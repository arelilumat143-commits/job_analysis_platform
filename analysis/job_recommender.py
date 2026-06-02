"""
岗位推荐模块。

基于 TF-IDF 文本向量与技能多热向量的余弦相似度，为指定职位或用户画像
推荐相似岗位，并支持按匹配度、期望城市与薪资综合排序。
"""

from __future__ import annotations

import re
from typing import Any, Literal

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from scipy.sparse import hstack

from analysis.data_cleaner import CITY_MAPPING
from analysis.skill_nlp import SkillNLPAnalyzer, skill_analyzer
from storage.database import DatabaseManager, db_manager

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# TF-IDF 与技能向量融合权重
_WEIGHT_TFIDF: float = 0.6
_WEIGHT_SKILL: float = 0.4

# 综合排序权重（匹配度 / 城市 / 薪资）
_WEIGHT_MATCH: float = 0.60
_WEIGHT_CITY: float = 0.25
_WEIGHT_SALARY: float = 0.15

SortMode = Literal["composite", "similarity", "salary", "city"]


# ---------------------------------------------------------------------------
# 岗位推荐器
# ---------------------------------------------------------------------------


class JobRecommender:
    """
    职位相似度推荐器。

    对库内全部职位构建「TF-IDF 文本向量 + 技能多热向量」的混合表示，
    通过余弦相似度检索最相似岗位，并按综合得分排序返回。
    """

    def __init__(
        self,
        db: DatabaseManager,
        skill_analyzer: SkillNLPAnalyzer,
    ) -> None:
        """
        Args:
            db: 数据库管理器，用于加载职位数据。
            skill_analyzer: 技能分析器，用于标准化技能标签与分词。
        """
        self._db = db
        self._skill_analyzer = skill_analyzer

        self._jobs: list[dict[str, Any]] = []
        self._job_index: dict[int, int] = {}
        self._tfidf_matrix: np.ndarray | None = None
        self._skill_matrix: np.ndarray | None = None
        self._combined_matrix: np.ndarray | None = None
        self._vectorizer: TfidfVectorizer | None = None
        self._skill_vocab: list[str] = []
        self._index_built: bool = False

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_city(city: str | None) -> str:
        """标准化城市名称。"""
        if not city or not str(city).strip():
            return "未知"
        raw = str(city).strip().replace("市", "")
        if "·" in raw:
            raw = raw.split("·", 1)[0].strip()
        return CITY_MAPPING.get(raw, CITY_MAPPING.get(raw + "市", raw))

    def _build_job_text(self, job: dict[str, Any]) -> str:
        """
        将职位拼接为 TF-IDF 语料文本。

        Args:
            job: 职位字典。

        Returns:
            用于向量化的空格分隔文本。
        """
        skills = self._skill_analyzer._extract_structured_skills(job)
        parts: list[str] = []

        for key in ("title", "description", "industry", "company"):
            value = job.get(key)
            if value:
                parts.append(str(value))

        city = self._normalize_city(job.get("city"))
        parts.append(city)

        if skills:
            parts.append(" ".join(skills))

        return " ".join(parts)

    def _extract_skills(self, job: dict[str, Any]) -> list[str]:
        """提取职位标准技能列表。"""
        return self._skill_analyzer._extract_structured_skills(job)

    def _build_index(self, force: bool = False) -> None:
        """
        构建 / 刷新职位向量索引。

        Args:
            force: 是否强制重建索引。
        """
        if self._index_built and not force:
            return

        jobs = self._db.get_all_jobs()
        self._jobs = jobs
        self._job_index = {
            int(job["id"]): idx
            for idx, job in enumerate(jobs)
            if job.get("id") is not None
        }

        if not jobs:
            self._tfidf_matrix = np.zeros((0, 1))
            self._skill_matrix = np.zeros((0, 1))
            self._combined_matrix = np.zeros((0, 1))
            self._skill_vocab = []
            self._index_built = True
            return

        corpus = [self._build_job_text(job) for job in jobs]

        self._vectorizer = TfidfVectorizer(
            max_features=2000,
            ngram_range=(1, 2),
            min_df=1,
            token_pattern=r"(?u)\b\w+\b",
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(corpus)

        # 构建全局技能词表
        vocab_set: set[str] = set()
        per_job_skills: list[list[str]] = []
        for job in jobs:
            skills = self._extract_skills(job)
            per_job_skills.append(skills)
            vocab_set.update(skills)

        self._skill_vocab = sorted(vocab_set)
        skill_index = {skill: i for i, skill in enumerate(self._skill_vocab)}

        skill_rows: list[list[float]] = []
        for skills in per_job_skills:
            row = [0.0] * len(self._skill_vocab)
            for skill in skills:
                if skill in skill_index:
                    row[skill_index[skill]] = 1.0
            skill_rows.append(row)

        self._skill_matrix = np.array(skill_rows, dtype=np.float64)
        if self._skill_matrix.size == 0:
            self._skill_matrix = np.zeros((len(jobs), 1))

        # L2 归一化后按权重拼接，用于余弦相似度
        tfidf_dense = normalize(self._tfidf_matrix, norm="l2", axis=1)
        tfidf_weighted = tfidf_dense.multiply(_WEIGHT_TFIDF)

        if not self._skill_vocab:
            self._combined_matrix = tfidf_weighted
        else:
            skill_norm = normalize(self._skill_matrix, norm="l2", axis=1)
            skill_weighted = skill_norm * _WEIGHT_SKILL
            self._combined_matrix = hstack([tfidf_weighted, skill_weighted])
        self._index_built = True

    def _vectorize_query(self, job: dict[str, Any]) -> np.ndarray:
        """
        将查询职位 / 用户画像转换为与索引一致的混合向量。

        Args:
            job: 职位或画像字典。

        Returns:
            1 × D 的查询向量（稀疏）。
        """
        if self._vectorizer is None:
            raise RuntimeError("索引未构建，请先加载职位数据")

        text = self._build_job_text(job)
        tfidf_vec = self._vectorizer.transform([text])
        tfidf_dense = normalize(tfidf_vec, norm="l2", axis=1)

        tfidf_weighted = tfidf_dense.multiply(_WEIGHT_TFIDF)

        if not self._skill_vocab:
            return tfidf_weighted

        skills = self._extract_skills(job)
        skill_row = [0.0] * len(self._skill_vocab)
        skill_index = {skill: i for i, skill in enumerate(self._skill_vocab)}
        for skill in skills:
            if skill in skill_index:
                skill_row[skill_index[skill]] = 1.0

        skill_vec = np.array([skill_row], dtype=np.float64)
        skill_norm = normalize(skill_vec, norm="l2", axis=1)
        skill_weighted = skill_norm * _WEIGHT_SKILL

        return hstack([tfidf_weighted, skill_weighted])

    def _resolve_job(
        self,
        job_id_or_dict: int | dict[str, Any],
    ) -> tuple[dict[str, Any], int | None]:
        """
        将 ``job_id`` 或职位字典解析为统一职位对象。

        Returns:
            ``(职位字典, 职位ID或None)``

        Raises:
            ValueError: 找不到对应职位。
        """
        self._build_index()

        if isinstance(job_id_or_dict, dict):
            job = job_id_or_dict
            job_id = job.get("id")
            if job_id is not None:
                job_id = int(job_id)
            return job, job_id

        job_id = int(job_id_or_dict)
        idx = self._job_index.get(job_id)
        if idx is None:
            raise ValueError(f"职位不存在: id={job_id}")
        return self._jobs[idx], job_id

    @staticmethod
    def _salary_mid(job: dict[str, Any]) -> float | None:
        """计算职位薪资中位数（K/月）。"""
        try:
            smin = float(job["salary_min"]) if job.get("salary_min") is not None else None
            smax = float(job["salary_max"]) if job.get("salary_max") is not None else None
        except (TypeError, ValueError):
            return None
        if smin is None or smax is None or smin <= 0 or smax <= 0:
            return None
        if smin > smax:
            smin, smax = smax, smin
        return (smin + smax) / 2.0

    def _city_match_score(
        self,
        job: dict[str, Any],
        preferred_city: str | None,
    ) -> float:
        """
        计算城市匹配得分。

        Args:
            job: 候选职位。
            preferred_city: 期望城市，``None`` 表示无偏好（得分为 0.5）。

        Returns:
            0.0 ~ 1.0 的匹配分数。
        """
        if not preferred_city:
            return 0.5

        job_city = self._normalize_city(job.get("city"))
        pref_city = self._normalize_city(preferred_city)
        return 1.0 if job_city == pref_city else 0.0

    def _salary_match_score(
        self,
        job: dict[str, Any],
        min_salary: float | None,
        max_salary: float | None,
    ) -> float:
        """
        计算薪资匹配得分。

        期望区间与职位薪资区间有重叠时得分较高；
        偏离越大得分越低。

        Returns:
            0.0 ~ 1.0 的匹配分数。
        """
        if min_salary is None and max_salary is None:
            return 0.5

        job_mid = self._salary_mid(job)
        if job_mid is None:
            return 0.3

        pref_min = float(min_salary) if min_salary is not None else 0.0
        pref_max = float(max_salary) if max_salary is not None else pref_min + 50.0
        if pref_min > pref_max:
            pref_min, pref_max = pref_max, pref_min

        pref_mid = (pref_min + pref_max) / 2.0
        overlap = min(pref_max, job_mid + 5) - max(pref_min, job_mid - 5)

        if overlap >= 0:
            return 1.0

        distance = min(abs(job_mid - pref_min), abs(job_mid - pref_max))
        return max(0.0, 1.0 - distance / max(pref_mid, 1.0))

    def _composite_score(
        self,
        similarity: float,
        city_score: float,
        salary_score: float,
    ) -> float:
        """按权重计算综合推荐得分。"""
        return (
            _WEIGHT_MATCH * similarity
            + _WEIGHT_CITY * city_score
            + _WEIGHT_SALARY * salary_score
        )

    def _rank_results(
        self,
        results: list[dict[str, Any]],
        sort_by: SortMode,
    ) -> list[dict[str, Any]]:
        """
        对推荐结果排序。

        Args:
            results: 含 ``similarity``、``composite_score`` 等字段的列表。
            sort_by: 排序方式。

        Returns:
            排序后的列表。
        """
        if sort_by == "similarity":
            key_fn = lambda item: item["similarity"]
        elif sort_by == "salary":
            key_fn = lambda item: item.get("salary_mid") or 0.0
        elif sort_by == "city":
            key_fn = lambda item: (item["city_match"], item["composite_score"])
        else:
            key_fn = lambda item: item["composite_score"]

        return sorted(results, key=key_fn, reverse=True)

    def _search_similar(
        self,
        query_job: dict[str, Any],
        *,
        exclude_job_id: int | None = None,
        top_n: int = 10,
        preferred_city: str | None = None,
        min_salary: float | None = None,
        max_salary: float | None = None,
        sort_by: SortMode = "composite",
    ) -> list[dict[str, Any]]:
        """
        内部相似度检索与综合排序。

        Args:
            query_job: 查询职位 / 画像字典。
            exclude_job_id: 需要排除的职位 ID（自身不推荐自身）。
            top_n: 返回条数。
            preferred_city: 期望城市（用于综合排序）。
            min_salary: 期望最低薪资（K/月）。
            max_salary: 期望最高薪资（K/月）。
            sort_by: 排序方式。

        Returns:
            推荐结果列表。
        """
        self._build_index()

        if not self._jobs or self._combined_matrix is None:
            return []

        query_vec = self._vectorize_query(query_job)
        similarities = cosine_similarity(query_vec, self._combined_matrix).flatten()

        # 画像中的偏好可覆盖参数
        pref_city = preferred_city or query_job.get("preferred_city") or query_job.get("city")
        pref_min = min_salary if min_salary is not None else query_job.get("min_salary")
        pref_max = max_salary if max_salary is not None else query_job.get("max_salary")

        results: list[dict[str, Any]] = []

        for idx, job in enumerate(self._jobs):
            job_id = job.get("id")
            if exclude_job_id is not None and job_id == exclude_job_id:
                continue

            similarity = float(similarities[idx])
            if similarity <= 0:
                continue

            city_score = self._city_match_score(job, pref_city)
            salary_score = self._salary_match_score(job, pref_min, pref_max)
            composite = self._composite_score(similarity, city_score, salary_score)

            results.append(
                {
                    "job": job,
                    "job_id": job_id,
                    "similarity": round(similarity, 4),
                    "composite_score": round(composite, 4),
                    "city_match": round(city_score, 4),
                    "salary_match": round(salary_score, 4),
                    "salary_mid": self._salary_mid(job),
                }
            )

        ranked = self._rank_results(results, sort_by)
        if top_n > 0:
            return ranked[:top_n]
        return ranked

    # ------------------------------------------------------------------
    # 对外推荐接口
    # ------------------------------------------------------------------

    def recommend_for_job(
        self,
        job_id_or_dict: int | dict[str, Any],
        top_n: int = 10,
        *,
        preferred_city: str | None = None,
        min_salary: float | None = None,
        max_salary: float | None = None,
        sort_by: SortMode = "composite",
    ) -> list[dict[str, Any]]:
        """
        基于指定职位推荐相似岗位。

        Args:
            job_id_or_dict: 职位 ID 或职位字典。
            top_n: 返回推荐条数。
            preferred_city: 优先推荐的城市（综合排序加权）。
            min_salary: 期望最低薪资（K/月）。
            max_salary: 期望最高薪资（K/月）。
            sort_by: 排序方式：``composite`` | ``similarity`` | ``salary`` | ``city``。

        Returns:
            推荐结果列表，每项含 ``job``、``similarity``、``composite_score`` 等字段。

        Raises:
            ValueError: 职位 ID 不存在。
        """
        query_job, exclude_id = self._resolve_job(job_id_or_dict)

        if preferred_city is None:
            preferred_city = query_job.get("city")

        return self._search_similar(
            query_job,
            exclude_job_id=exclude_id,
            top_n=top_n,
            preferred_city=preferred_city,
            min_salary=min_salary,
            max_salary=max_salary,
            sort_by=sort_by,
        )

    def recommend_for_profile(
        self,
        profile_dict: dict[str, Any],
        top_n: int = 10,
        *,
        sort_by: SortMode = "composite",
    ) -> list[dict[str, Any]]:
        """
        基于用户画像推荐岗位。

        ``profile_dict`` 支持字段示例::

            {
                "skills": ["Python", "Django"],
                "city": "北京",
                "preferred_city": "北京",
                "min_salary": 20,
                "max_salary": 35,
                "experience": "3-5年",
                "education": "本科",
                "title": "Python开发",
                "industry": "互联网",
            }

        Args:
            profile_dict: 用户技能与求职偏好。
            top_n: 返回推荐条数。
            sort_by: 排序方式。

        Returns:
            推荐结果列表（结构同 ``recommend_for_job``）。
        """
        query_job = self._profile_to_job(profile_dict)
        return self._search_similar(
            query_job,
            exclude_job_id=None,
            top_n=top_n,
            preferred_city=profile_dict.get("preferred_city") or profile_dict.get("city"),
            min_salary=profile_dict.get("min_salary"),
            max_salary=profile_dict.get("max_salary"),
            sort_by=sort_by,
        )

    def get_similar_jobs(
        self,
        job_id: int,
        top_n: int = 5,
        *,
        sort_by: SortMode = "composite",
    ) -> list[dict[str, Any]]:
        """
        获取与指定职位最相似的岗位（简化的 ``recommend_for_job`` 封装）。

        Args:
            job_id: 职位主键 ID。
            top_n: 返回条数，默认 5。
            sort_by: 排序方式。

        Returns:
            相似职位推荐列表。
        """
        return self.recommend_for_job(
            job_id,
            top_n=top_n,
            sort_by=sort_by,
        )

    @staticmethod
    def _profile_to_job(profile_dict: dict[str, Any]) -> dict[str, Any]:
        """
        将用户画像字典转换为伪职位字典，供向量化使用。

        Args:
            profile_dict: 用户画像。

        Returns:
            与职位结构兼容的字典。
        """
        skills = profile_dict.get("skills") or []
        if isinstance(skills, str):
            skills = [s.strip() for s in re.split(r"[,，、;；|/]", skills) if s.strip()]

        description_parts = [
            str(profile_dict.get("title") or ""),
            str(profile_dict.get("industry") or ""),
            str(profile_dict.get("experience") or ""),
            str(profile_dict.get("education") or ""),
            " ".join(skills),
        ]

        return {
            "title": profile_dict.get("title") or "求职意向",
            "company": profile_dict.get("company") or "",
            "city": profile_dict.get("city") or profile_dict.get("preferred_city"),
            "industry": profile_dict.get("industry"),
            "experience": profile_dict.get("experience"),
            "education": profile_dict.get("education"),
            "skills": skills,
            "description": " ".join(p for p in description_parts if p),
            "salary_min": profile_dict.get("min_salary"),
            "salary_max": profile_dict.get("max_salary"),
            "preferred_city": profile_dict.get("preferred_city"),
            "min_salary": profile_dict.get("min_salary"),
            "max_salary": profile_dict.get("max_salary"),
        }

    def refresh_index(self) -> int:
        """
        强制刷新职位向量索引。

        Returns:
            当前索引中的职位数量。
        """
        self._build_index(force=True)
        return len(self._jobs)


# 全局实例：项目内统一引用
job_recommender = JobRecommender(db_manager, skill_analyzer)
