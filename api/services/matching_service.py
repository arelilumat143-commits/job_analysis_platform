# ============================================================================
# 岗位匹配服务 v2 — 双引擎架构（TF-IDF + SBERT）
# 参考 resume-scanner-api 的核心设计：
#   - Strict Mode: TF-IDF 精确关键词匹配（模拟 ATS 筛选）
#   - Flexible Mode: SBERT 语义匹配（理解上下文，"Python" ≈ "编程"）
#   - 关键词提取 + 缺失技能分析 + 关键技能安全校验
# ============================================================================
from __future__ import annotations

import json
import logging
import re
import sys
import threading
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 将项目根加入搜索路径
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from analysis.salary_predictor_v2 import _SKILL_CATEGORIES, _SKILL_KEYWORD_TO_CAT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SBERT 模型（延迟加载 + 全局缓存，避免每次请求都重新加载）
# ---------------------------------------------------------------------------
_embed_model = None
_embed_lock = threading.Lock()
# 使用多语言轻量模型，支持中英文混合语义理解（384维向量）
_SBERT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def _get_embed_model():
    """懒加载 SBERT 模型（线程安全）"""
    global _embed_model
    if _embed_model is None:
        with _embed_lock:
            if _embed_model is None:
                from sentence_transformers import SentenceTransformer
                logger.info("正在加载 SBERT 模型: %s", _SBERT_MODEL_NAME)
                _embed_model = SentenceTransformer(_SBERT_MODEL_NAME)
                logger.info("SBERT 模型加载完成")
    return _embed_model


# ---------------------------------------------------------------------------
# 文本预处理（参考 resume-scanner-api 的 clean_text）
# ---------------------------------------------------------------------------
def _clean_text(text: str) -> str:
    """清洗文本：去换行、合并空格、去首尾空白"""
    text = text.replace("\\n", " ")
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# 核心技能（匹配加分权重 ×1.5）
# ---------------------------------------------------------------------------
_CORE_SKILLS: set[str] = {
    "python", "java", "golang", "go", "c++", "cpp", "c", "rust",
    "javascript", "js", "typescript", "ts",
    "sql", "mysql", "postgresql", "oracle", "mongodb", "redis",
    "spring", "django", "flask", "fastapi", "react", "vue", "angular",
    "docker", "kubernetes", "k8s", "linux",
    "tensorflow", "pytorch", "spark", "hadoop", "kafka",
}

# ---------------------------------------------------------------------------
# 技能分类别名 → 子技能展开（模糊匹配用）
# ---------------------------------------------------------------------------
_CATEGORY_ALIASES = {
    "前端": "frontend", "后端": "backend", "移动端": "mobile",
    "移动开发": "mobile", "安卓": "mobile", "ios开发": "mobile",
    "人工智能": "ai", "ai": "ai", "机器学习": "ai", "深度学习": "ai",
    "大数据": "data", "数据分析": "data", "数据工程": "data",
    "运维": "devops", "devops": "devops", "云计算": "cloud",
    "云原生": "cloud", "云服务": "cloud",
}
_CATEGORY_NAME_TO_KEYWORDS: dict[str, list[str]] = {}
for _cat, _kws in _SKILL_CATEGORIES.items():
    _CATEGORY_NAME_TO_KEYWORDS[_cat] = _kws


class JobMatchingService:
    """
    岗位匹配服务 v2 — TF-IDF + SBERT 双引擎。

    - Strict Mode: 精确技能关键词匹配（TF-IDF Cosine Similarity）
    - Flexible Mode: SBERT 语义嵌入匹配（理解上下文相关性）
    - 综合评分: TF-IDF(30%) + SBERT(30%) + 自定义因子(40%)
    - 关键词提取 + 缺失技能分析 + 关键技能校验

    使用方式:
        svc = JobMatchingService()
        results = svc.match(skills=["Python","Django"], city="北京", top_n=10)
    """

    def __init__(self) -> None:
        # TF-IDF 向量化器
        self._tfidf = TfidfVectorizer(
            token_pattern=r"[^\s,，、;；|/]+",
            lowercase=True,
            max_features=2000,
            stop_words=None,  # 不过滤停用词，技能名都很短
        )
        self._tfidf_matrix: Any = None
        self._job_skills: dict[int, list[str]] = {}   # job_id → 技能列表
        self._job_info: dict[int, dict] = {}           # job_id → 完整岗位信息
        self._job_ids: list[int] = []                  # 与矩阵行对应的 ID
        self._job_skill_docs: list[str] = []           # 技能文本（用于 TF-IDF）
        self._job_full_docs: list[str] = []            # 完整岗位描述（用于 SBERT）
        self._sbert_embeddings: Any = None             # SBERT 嵌入矩阵
        self._fitted = False
        self._sbert_ready = False

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------
    def reload_index(self) -> None:
        """从数据库加载所有岗位，构建 TF-IDF + SBERT 双索引"""
        from storage.database import db_manager

        logger.info("开始构建双引擎索引（TF-IDF + SBERT）...")
        self._job_skills.clear()
        self._job_info.clear()
        self._job_ids.clear()
        self._job_skill_docs.clear()
        self._job_full_docs.clear()

        try:
            jobs = db_manager.get_all_jobs()
        except Exception as exc:
            logger.error("获取岗位数据失败: %s", exc)
            return

        for job in jobs:
            jid = int(job["id"])
            raw_skills = self._parse_skills(job.get("skills"))
            self._job_skills[jid] = raw_skills
            self._job_info[jid] = job
            self._job_ids.append(jid)

            # 技能文档：纯技能列表拼接（TF-IDF 用）
            skill_doc = " ".join(raw_skills) if raw_skills else ""
            self._job_skill_docs.append(skill_doc)

            # 完整文档：标题 + 技能 + 公司 + 经验/学历要求（SBERT 用）
            full_doc = self._build_full_doc(job, raw_skills)
            self._job_full_docs.append(full_doc)

        # 构建 TF-IDF 矩阵
        if self._job_skill_docs:
            self._tfidf_matrix = self._tfidf.fit_transform(self._job_skill_docs)
        self._fitted = True

        # 构建 SBERT 嵌入（异步加载，不阻塞首次查询）
        self._build_sbert_index()
        logger.info("双引擎索引构建完成: %d 个岗位", len(self._job_ids))

    def _build_sbert_index(self) -> None:
        """构建 SBERT 语义嵌入索引（对完整岗位描述编码）"""
        try:
            model = _get_embed_model()
            # 对完整文档批量编码 → N×384 矩阵
            self._sbert_embeddings = model.encode(
                self._job_full_docs,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            self._sbert_ready = True
            logger.info("SBERT 索引构建完成: %d 条嵌入", len(self._job_full_docs))
        except Exception as exc:
            logger.warning("SBERT 索引构建失败（将回退到纯 TF-IDF 模式）: %s", exc)
            self._sbert_ready = False

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_skills(raw_skills: Any) -> list[str]:
        """标准化技能数据 → 字符串列表"""
        if isinstance(raw_skills, str):
            try:
                parsed = json.loads(raw_skills)
                if isinstance(parsed, list):
                    return [str(s) for s in parsed if s]
                return [str(parsed)]
            except (json.JSONDecodeError, TypeError):
                return [s.strip() for s in re.split(r"[,，、;；|/]", raw_skills) if s.strip()]
        elif isinstance(raw_skills, list):
            return [str(s) for s in raw_skills if s]
        return []

    @staticmethod
    def _build_full_doc(job: dict, skills: list[str]) -> str:
        """构建岗位完整描述文本（供 SBERT 语义编码用）"""
        parts = [
            str(job.get("title", "")),
            " ".join(skills),
        ]
        # 有值才加入
        for key in ["company", "city", "industry", "experience", "education"]:
            val = job.get(key)
            if val and str(val).strip():
                parts.append(str(val).strip())
        doc = " ".join(parts)
        return _clean_text(doc)

    # ------------------------------------------------------------------
    # 技能展开（模糊匹配）
    # ------------------------------------------------------------------
    def _expand_skills(self, user_skills: list[str]) -> list[str]:
        """将用户输入的类别名展开为具体技能列表"""
        expanded: set[str] = set()
        for skill in user_skills:
            key = skill.lower().strip()
            cat = _CATEGORY_ALIASES.get(key) or key
            if cat in _CATEGORY_NAME_TO_KEYWORDS:
                for kw in _CATEGORY_NAME_TO_KEYWORDS[cat]:
                    expanded.add(kw.lower())
            else:
                expanded.add(key)
        return list(expanded)

    # ------------------------------------------------------------------
    # 关键词提取（参考 resume-scanner-api 的 TF-IDF 关键词分析）
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_keywords_from_skills(skills: list[str], top_n: int = 10) -> list[str]:
        """
        从技能列表中提取关键词（按 TF-IDF 重要性排序）。
        使用文档频率倒数（IDF）思路，但技能列表通常很短，
        这里直接返回去重后的技能列表。
        """
        seen = set()
        result = []
        for s in skills:
            key = s.lower().strip()
            if key and key not in seen:
                seen.add(key)
                result.append(key)
        return result[:top_n]

    # ------------------------------------------------------------------
    # 核心匹配方法
    # ------------------------------------------------------------------
    def match(
        self,
        skills: list[str],
        city: str,
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """
        岗位智能匹配（双引擎）。

        Args:
            skills: 用户技能列表
            city: 期望城市
            salary_min: 期望最低薪资（K/月）
            salary_max: 期望最高薪资（K/月）
            top_n: 返回前 N 个最佳匹配

        Returns:
            dict: { total_jobs_scanned, matched_count, top_matches, user_skills,
                    mode, keyword_analysis }
        """
        if not self._fitted:
            self.reload_index()

        if not self._job_ids:
            return {
                "total_jobs_scanned": 0, "matched_count": 0,
                "top_matches": [], "user_skills": skills,
                "mode": "offline", "keyword_analysis": {},
            }

        # 展开模糊匹配技能
        expanded_skills = self._expand_skills(skills)
        user_skill_str = " ".join(expanded_skills)

        # ── Phase 1: TF-IDF 精确匹配 ──
        tfidf_scores = np.zeros(len(self._job_ids))
        try:
            user_vec = self._tfidf.transform([user_skill_str])
            tfidf_scores = cosine_similarity(user_vec, self._tfidf_matrix).flatten()
        except Exception as exc:
            logger.error("TF-IDF 计算失败: %s", exc)

        # ── Phase 2: SBERT 语义匹配 ──
        sbert_scores = np.zeros(len(self._job_ids))
        sbert_used = False
        if self._sbert_ready and self._sbert_embeddings is not None:
            try:
                model = _get_embed_model()
                user_full_doc = _clean_text(
                    f"技能: {' '.join(expanded_skills)} 城市: {city}"
                )
                user_embed = model.encode([user_full_doc], convert_to_numpy=True)
                from sklearn.metrics.pairwise import cosine_similarity as cos_sim
                sbert_scores = cos_sim(user_embed, self._sbert_embeddings).flatten()
                sbert_used = True
            except Exception as exc:
                logger.warning("SBERT 编码失败，回退到 TF-IDF 模式: %s", exc)

        # ── Phase 3: 综合评分 ──
        results: list[dict[str, Any]] = []
        all_matched_skills_set: set[str] = set()

        for i, job_id in enumerate(self._job_ids):
            job_info = self._job_info[job_id]
            job_skills = self._job_skills.get(job_id, [])

            # 技能精确匹配
            matched_skills, skill_coverage, weighted_skill_score = self._calc_skill_match(
                expanded_skills, job_skills, tfidf_scores[i]
            )

            # 跟踪所有被匹配的技能
            all_matched_skills_set.update(matched_skills)

            # 城市匹配
            city_score = self._calc_city_match(city, str(job_info.get("city", "")))
            # 薪资匹配
            salary_score = self._calc_salary_match(salary_min, salary_max, job_info)

            # 综合评分：
            #   TF-IDF: 30% | SBERT: 30% | 技能加权: 20% | 城市: 10% | 薪资: 10%
            tfidf_weight = 0.30 if sbert_used else 0.50
            sbert_weight = 0.30 if sbert_used else 0.0
            skill_weight = 0.20
            city_weight = 0.10
            salary_weight = 0.10

            if sbert_used:
                composite = (
                    tfidf_scores[i] * tfidf_weight +
                    sbert_scores[i] * sbert_weight +
                    weighted_skill_score * skill_weight +
                    city_score * city_weight +
                    salary_score * salary_weight
                )
            else:
                # 回退模式：TF-IDF 权重提升
                composite = (
                    tfidf_scores[i] * 0.50 +
                    weighted_skill_score * 0.30 +
                    city_score * 0.10 +
                    salary_score * 0.10
                )

            # 至少匹配上1个技能或城市强匹配才纳入结果
            if matched_skills or city_score >= 0.5:
                # 分项得分明细（用于前端可解释性展示）
                if sbert_used:
                    breakdown = {
                        "tfidf": round(float(tfidf_scores[i]) * 100 * tfidf_weight, 1),
                        "sbert": round(float(sbert_scores[i]) * 100 * sbert_weight, 1),
                        "skill": round(weighted_skill_score * 100 * skill_weight, 1),
                        "city": round(city_score * 100 * city_weight, 1),
                        "salary": round(salary_score * 100 * salary_weight, 1),
                    }
                else:
                    breakdown = {
                        "tfidf": round(float(tfidf_scores[i]) * 100 * 0.50, 1),
                        "sbert": 0,
                        "skill": round(weighted_skill_score * 100 * 0.30, 1),
                        "city": round(city_score * 100 * 0.10, 1),
                        "salary": round(salary_score * 100 * 0.10, 1),
                    }
                results.append({
                    "job": job_info,
                    "score": round(composite * 100, 1),
                    "tfidf_score": round(float(tfidf_scores[i]) * 100, 1),
                    "sbert_score": round(float(sbert_scores[i]) * 100, 1) if sbert_used else None,
                    "matched_skills": matched_skills,
                    "skill_coverage": round(skill_coverage, 3),
                    "city_match": city_score >= 0.7,
                    "salary_match": salary_score >= 0.6,
                    "score_breakdown": breakdown,
                })

        # 按综合分降序排序
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = results[:top_n]

        # ── Phase 4: 关键词分析 + 缺失技能检测（参考 resume-scanner-api）──
        # 提取用户技能中的"关键技能"
        critical_keywords = self._extract_keywords_from_skills(expanded_skills)
        # 提取已有岗位中出现的高频技能作为参考
        job_skill_freq: dict[str, int] = {}
        for jskills in self._job_skills.values():
            for s in jskills:
                key = s.lower().strip()
                job_skill_freq[key] = job_skill_freq.get(key, 0) + 1
        # Top 20 高频技能
        top_job_skills = sorted(job_skill_freq.items(), key=lambda x: x[1], reverse=True)[:20]
        available_keywords = [k for k, v in top_job_skills]

        # 缺失技能：高频技能中用户没有的
        missing_keywords = [k for k, v in top_job_skills
                           if k not in {s.lower() for s in expanded_skills}][:10]

        # ── Phase 5: 组装返回 ──
        matched_jobs = []
        for r in top_results:
            job = r["job"]
            smin = job.get("salary_min")
            smax = job.get("salary_max")
            matched_jobs.append({
                "job_id": int(job["id"]),
                "title": str(job.get("title", "")),
                "company": str(job.get("company", "")),
                "city": str(job.get("city", "")),
                "salary_min": round(float(smin), 1) if smin is not None else None,
                "salary_max": round(float(smax), 1) if smax is not None else None,
                "required_skills": self._job_skills.get(job["id"], []),
                "experience": str(job.get("experience", "") or ""),
                "education": str(job.get("education", "") or ""),
                "score": r["score"],
                "tfidf_score": r["tfidf_score"],
                "sbert_score": r["sbert_score"],
                "score_breakdown": r["score_breakdown"],
                "reasons": {
                    "skill_match": r["matched_skills"],
                    "skill_coverage": r["skill_coverage"],
                    "city_match": r["city_match"],
                    "salary_match": r["salary_match"],
                },
            })

        return {
            "total_jobs_scanned": len(self._job_ids),
            "matched_count": len(matched_jobs),
            "top_matches": matched_jobs,
            "user_skills": expanded_skills,
            "mode": "dual_engine" if sbert_used else "tfidf_only",
            "keyword_analysis": {
                "critical_keywords": critical_keywords,
                "available_keywords": available_keywords,
                "missing_keywords": missing_keywords,
                "total_unique_skills": len(job_skill_freq),
            },
        }

    # ------------------------------------------------------------------
    # 技能匹配评分
    # ------------------------------------------------------------------
    def _calc_skill_match(
        self,
        user_skills: list[str],
        job_skills: list[str],
        cosine_sim: float,
    ) -> tuple[list[str], float, float]:
        """
        计算技能匹配详细得分。

        Returns:
            (matched_skills, skill_coverage, weighted_score)
        """
        user_set = {s.lower().strip() for s in user_skills}
        job_set = {s.lower().strip() for s in job_skills}
        matched = user_set & job_set
        matched_list = sorted(matched)

        if len(user_set) == 0:
            return matched_list, 0.0, cosine_sim

        # 覆盖率
        coverage = len(matched) / len(user_set)

        # 加权：核心技能 ×1.5
        core_weight = sum(1.5 for s in matched if s in _CORE_SKILLS)
        normal_weight = sum(1.0 for s in matched if s not in _CORE_SKILLS)
        max_core = sum(1.5 for s in user_set if s in _CORE_SKILLS)
        max_normal = sum(1.0 for s in user_set if s not in _CORE_SKILLS)
        max_weight = max_core + max_normal

        if max_weight == 0:
            weighted_score = cosine_sim
        else:
            actual = core_weight + normal_weight
            weighted_score = (actual / max_weight) * 0.6 + cosine_sim * 0.4

        return matched_list, coverage, weighted_score

    # ------------------------------------------------------------------
    # 城市匹配
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_city_match(user_city: str, job_city: str) -> float:
        uc = user_city.strip().rstrip("市").lower()
        jc = (job_city or "").strip().rstrip("市").lower()
        if not uc or not jc:
            return 0.5
        if uc == jc:
            return 1.0
        if uc in jc or jc in uc:
            return 0.7
        return 0.0

    # ------------------------------------------------------------------
    # 薪资匹配
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_salary_match(
        user_min: Optional[float],
        user_max: Optional[float],
        job: dict[str, Any],
    ) -> float:
        try:
            jmin = float(job.get("salary_min")) if job.get("salary_min") is not None else None
            jmax = float(job.get("salary_max")) if job.get("salary_max") is not None else None
        except (TypeError, ValueError):
            return 0.5
        if jmin is None or jmax is None or jmin <= 0 or jmax <= 0:
            return 0.5
        if jmin > jmax:
            jmin, jmax = jmax, jmin

        umin = float(user_min) if user_min is not None and user_min > 0 else None
        umax = float(user_max) if user_max is not None and user_max > 0 else None
        if umin is None and umax is None:
            return 0.7

        if umin is not None and umax is not None:
            overlap_low = max(umin, jmin)
            overlap_high = min(umax, jmax)
            if overlap_low <= overlap_high:
                user_range = umax - umin
                overlap_range = overlap_high - overlap_low
                return min(1.0, overlap_range / user_range if user_range > 0 else 1.0)
            else:
                gap = jmin - umax if umax < jmin else umin - jmax
                return max(0.0, 1.0 - gap / max(umin, jmin, 1.0))
        elif umin is not None:
            return min(1.0, max(0.0, (jmax - umin) / max(jmax, umin, 1.0) + 0.5))
        else:
            return min(1.0, max(0.0, (umax - jmin) / max(umax, jmin, 1.0) + 0.5))


# 全局单例
job_matching_service = JobMatchingService()
