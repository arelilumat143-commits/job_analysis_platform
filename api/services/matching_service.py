# ============================================================================
# 岗位匹配服务
# 基于 TF-IDF + Cosine Similarity，支持技能加权和模糊匹配
# ============================================================================
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 将项目根加入搜索路径，以复用 analysis 模块的技能分类体系
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from analysis.salary_predictor_v2 import _SKILL_CATEGORIES, _SKILL_KEYWORD_TO_CAT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 核心技能（匹配时加权 ×1.5）
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
# 技能分类 → 用户输入关键词的反向映射（用于模糊匹配）
#   用户输入类别名（如 "前端"）时，自动展开为子技能
# ---------------------------------------------------------------------------
_CATEGORY_NAME_TO_KEYWORDS: dict[str, list[str]] = {}
for _cat, _kws in _SKILL_CATEGORIES.items():
    _CATEGORY_NAME_TO_KEYWORDS[_cat] = _kws
# 补充中文类别名映射
_CATEGORY_ALIASES = {
    "前端": "frontend", "后端": "backend", "移动端": "mobile",
    "移动开发": "mobile", "安卓": "mobile", "ios开发": "mobile",
    "人工智能": "ai", "ai": "ai", "机器学习": "ai", "深度学习": "ai",
    "大数据": "data", "数据分析": "data", "数据工程": "data",
    "运维": "devops", "devops": "devops", "云计算": "cloud",
    "云原生": "cloud", "云服务": "cloud",
}


class JobMatchingService:
    """
    岗位匹配服务 — 基于 TF-IDF + Cosine Similarity。

    使用方式:
        svc = JobMatchingService()
        results = svc.match(skills=["Python","Django"], city="北京", top_n=10)
    """

    def __init__(self) -> None:
        # TF-IDF 向量化器（中文技能名可能含空格，用自定义分词）
        self._tfidf = TfidfVectorizer(
            token_pattern=r"[^\s,，、;；|/]+",
            lowercase=True,
            max_features=2000,
        )
        self._tfidf_matrix: Any = None          # 岗位技能的 TF-IDF 矩阵
        self._job_skills: dict[int, list[str]] = {}  # job_id → 技能列表
        self._job_info: dict[int, dict] = {}        # job_id → 完整信息
        self._job_ids: list[int] = []               # 与 TF-IDF 行对应的 job_id
        self._fitted = False

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------
    def reload_index(self) -> None:
        """从数据库重新加载所有岗位的技能的 TF-IDF 索引"""
        from storage.database import db_manager

        logger.info("开始构建岗位 TF-IDF 索引...")
        self._job_skills.clear()
        self._job_info.clear()
        self._job_ids.clear()

        try:
            jobs = db_manager.get_all_jobs()
        except Exception as exc:
            logger.error("获取岗位数据失败: %s", exc)
            return

        skill_docs: list[str] = []
        for job in jobs:
            jid = int(job["id"])
            raw_skills = job.get("skills") or []

            # 标准化技能列表：统一转为字符串列表
            if isinstance(raw_skills, str):
                try:
                    parsed = json.loads(raw_skills)
                    if isinstance(parsed, list):
                        raw_skills = [str(s) for s in parsed if s]
                    else:
                        raw_skills = [str(parsed)]
                except (json.JSONDecodeError, TypeError):
                    raw_skills = [s.strip() for s in re.split(r"[,，、;；|/]", raw_skills) if s.strip()]
            elif isinstance(raw_skills, list):
                raw_skills = [str(s) for s in raw_skills if s]
            else:
                raw_skills = []

            self._job_skills[jid] = raw_skills
            self._job_info[jid] = job
            self._job_ids.append(jid)
            # 将技能列表拼接为文本，供 TF-IDF 处理
            skill_docs.append(" ".join(raw_skills) if raw_skills else "")

        if skill_docs:
            self._tfidf_matrix = self._tfidf.fit_transform(skill_docs)
        self._fitted = True
        logger.info("TF-IDF 索引构建完成: %d 个岗位", len(self._job_ids))

    # ------------------------------------------------------------------
    # 模糊匹配：将用户输入展开为具体技能
    # ------------------------------------------------------------------
    def _expand_skills(self, user_skills: list[str]) -> list[str]:
        """
        展开用户技能输入，支持类别名模糊匹配。

        例如：
            ["前端"] → ["javascript", "typescript", "vue", "react", ...]
            ["ai"]   → ["机器学习", "深度学习", "pytorch", ...]
        """
        expanded: set[str] = set()
        for skill in user_skills:
            key = skill.lower().strip()
            # 检查是否为类别别名
            cat = _CATEGORY_ALIASES.get(key) or key
            if cat in _CATEGORY_NAME_TO_KEYWORDS:
                # 展开为类别下所有子技能
                for kw in _CATEGORY_NAME_TO_KEYWORDS[cat]:
                    expanded.add(kw.lower())
            else:
                expanded.add(key)

        # 返回去重后的所有技能
        return list(expanded)

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

        Args:
            user_skills: 用户输入的技能列表（已展开）
            job_skills: 岗位要求的技能列表
            cosine_sim: 上一轮 TF-IDF 余弦相似度

        Returns:
            (matched_skills: 匹配上的技能,
             skill_coverage: 用户技能覆盖率,
             weighted_score: 加权后的匹配分 0-1)
        """
        user_set = {s.lower().strip() for s in user_skills}
        job_set = {s.lower().strip() for s in job_skills}

        # 交集 = 匹配上的技能
        matched = user_set & job_set
        matched_list = sorted(matched)

        # 覆盖率（从用户角度，匹配了多少技能）
        if len(user_set) == 0:
            coverage = 0.0
        else:
            coverage = len(matched) / len(user_set)

        # 加权评分：
        #   - 核心技能匹配权重 ×1.5
        #   - 非核心技能 ×1.0
        core_weight_total = sum(1.5 for s in matched if s in _CORE_SKILLS)
        normal_weight_total = sum(1.0 for s in matched if s not in _CORE_SKILLS)

        # 用户技能总数对应的最大可能加权得分
        max_core = sum(1.5 for s in user_set if s in _CORE_SKILLS)
        max_normal = sum(1.0 for s in user_set if s not in _CORE_SKILLS)
        max_weight = max_core + max_normal

        if max_weight == 0:
            weighted_score = cosine_sim  # 回退到纯 TF-IDF
        else:
            actual_weight = core_weight_total + normal_weight_total
            weighted_score = (actual_weight / max_weight) * 0.6 + cosine_sim * 0.4

        return matched_list, coverage, weighted_score

    # ------------------------------------------------------------------
    # 城市匹配
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_city_match(user_city: str, job_city: str) -> float:
        """
        城市匹配度。

        精确匹配城市名称（去除"市"后缀后比较）。
        返回 0-1 的匹配度。
        """
        uc = user_city.strip().rstrip("市").lower()
        jc = (job_city or "").strip().rstrip("市").lower()

        if not uc or not jc:
            return 0.5  # 无信息时给中性分

        if uc == jc:
            return 1.0
        # 部分匹配（如 "北京朝阳" 包含 "北京"）
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
        """
        薪资匹配度。

        检查岗位薪资范围与用户期望的重叠程度。
        返回 0-1 的匹配度。
        """
        job_min = job.get("salary_min")
        job_max = job.get("salary_max")

        # 转换类型
        try:
            jmin = float(job_min) if job_min is not None else None
            jmax = float(job_max) if job_max is not None else None
        except (TypeError, ValueError):
            return 0.5  # 无法判断时给中性分

        if jmin is None or jmax is None or jmin <= 0 or jmax <= 0:
            return 0.5
        if jmin > jmax:
            jmin, jmax = jmax, jmin

        umin = float(user_min) if user_min is not None and user_min > 0 else None
        umax = float(user_max) if user_max is not None and user_max > 0 else None

        # 用户未设薪资期望 → 中性分
        if umin is None and umax is None:
            return 0.7

        # 计算重叠区间
        if umin is not None and umax is not None:
            overlap_low = max(umin, jmin)
            overlap_high = min(umax, jmax)
            if overlap_low <= overlap_high:
                # 有重叠：重叠占用户区间的比例
                user_range = umax - umin
                overlap_range = overlap_high - overlap_low
                return min(1.0, overlap_range / user_range if user_range > 0 else 1.0)
            else:
                # 无重叠：按距离衰减
                if umax < jmin:
                    gap = jmin - umax
                else:
                    gap = umin - jmax
                return max(0.0, 1.0 - gap / max(umin, jmin, 1.0))
        elif umin is not None:
            # 用户只设最低薪资
            return min(1.0, max(0.0, (jmax - umin) / max(jmax, umin, 1.0) + 0.5))
        else:
            # 用户只设最高薪资
            return min(1.0, max(0.0, (umax - jmin) / max(umax, jmin, 1.0) + 0.5))

    # ------------------------------------------------------------------
    # 主匹配方法
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
        岗位匹配主方法。

        Args:
            skills: 用户技能列表
            city: 期望城市
            salary_min: 期望最低薪资（K/月），可选
            salary_max: 期望最高薪资（K/月），可选
            top_n: 返回前 N 个最佳匹配

        Returns:
            dict: {
                total_jobs_scanned: 扫描岗位总数,
                matched_count: 匹配到的岗位数量,
                top_matches: [MatchedJob, ...],
                user_skills: 标准化后的用户技能,
            }
        """
        # 确保索引已构建
        if not self._fitted:
            self.reload_index()

        if not self._job_ids:
            return {
                "total_jobs_scanned": 0,
                "matched_count": 0,
                "top_matches": [],
                "user_skills": skills,
            }

        # 展开用户技能（模糊匹配 → 具体技能）
        expanded_skills = self._expand_skills(skills)
        user_skill_str = " ".join(expanded_skills)

        # TF-IDF + Cosine Similarity
        try:
            user_vec = self._tfidf.transform([user_skill_str])
            cosine_scores = cosine_similarity(user_vec, self._tfidf_matrix).flatten()
        except Exception as exc:
            logger.error("TF-IDF 向量计算失败: %s", exc)
            return {
                "total_jobs_scanned": len(self._job_ids),
                "matched_count": 0,
                "top_matches": [],
                "user_skills": expanded_skills,
            }

        # 逐岗位计算综合评分
        results: list[dict[str, Any]] = []
        for i, job_id in enumerate(self._job_ids):
            job_info = self._job_info[job_id]
            job_skills = self._job_skills.get(job_id, [])

            # 技能匹配
            matched_skills, skill_coverage, skill_score = self._calc_skill_match(
                expanded_skills, job_skills, cosine_scores[i]
            )

            # 城市匹配
            city_score = self._calc_city_match(city, str(job_info.get("city", "")))

            # 薪资匹配
            salary_score = self._calc_salary_match(salary_min, salary_max, job_info)

            # 综合评分：技能50% + 城市20% + 薪资30%
            composite = skill_score * 0.5 + city_score * 0.2 + salary_score * 0.3

            # 至少匹配上1个技能或城市匹配才纳入结果
            if matched_skills or city_score >= 0.5:
                results.append({
                    "job": job_info,
                    "score": round(composite * 100, 1),
                    "matched_skills": matched_skills,
                    "skill_coverage": round(skill_coverage, 3),
                    "city_match": city_score >= 0.7,
                    "salary_match": salary_score >= 0.6,
                })

        # 按综合分降序排序，取前 top_n
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = results[:top_n]

        # 组装返回结果
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
                "score": r["score"],
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
        }


# 全局单例
job_matching_service = JobMatchingService()
