"""
技能 NLP 分析模块。

基于 ``jobs`` / ``jobs_cleaned`` 表中的技能标签与职位描述文本，
使用 jieba 分词与 TF-IDF 提取技能关键词，并统计频率、共现、关联规则与趋势。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any

import jieba
from sklearn.feature_extraction.text import TfidfVectorizer

from analysis.data_cleaner import SKILL_MAPPING
from storage.database import DatabaseManager, db_manager

# ---------------------------------------------------------------------------
# 常量与词典
# ---------------------------------------------------------------------------

# 已知技能标准名集合（来自清洗模块映射表）
_KNOWN_SKILLS: set[str] = set(SKILL_MAPPING.values())

# 分词停用词（招聘描述中的常见无意义词）
_STOPWORDS: frozenset[str] = frozenset(
    {
        "的",
        "和",
        "与",
        "及",
        "等",
        "有",
        "具备",
        "熟悉",
        "了解",
        "掌握",
        "精通",
        "使用",
        "相关",
        "经验",
        "能力",
        "优先",
        "要求",
        "负责",
        "工作",
        "岗位",
        "任职",
        "招聘",
        "公司",
        "团队",
        "项目",
        "开发",
        "设计",
        "实现",
        "完成",
        "参与",
        "支持",
        "进行",
        "以上",
        "以下",
        "不限",
        "良好",
        "较强",
        "扎实",
    }
)

# 趋势分析：近期窗口天数
_TREND_RECENT_DAYS = 30

# 技能 token 匹配（英文技术词）
_SKILL_TOKEN_PATTERN = re.compile(r"^[a-zA-Z+#.][\w+#.]*$")


# ---------------------------------------------------------------------------
# 技能 NLP 分析器
# ---------------------------------------------------------------------------


class SkillNLPAnalyzer:
    """
    技能自然语言处理分析器。

    从数据库加载职位数据，结合结构化 ``skills`` 字段与描述文本 TF-IDF，
    提供频率统计、共现分析、关联规则挖掘与趋势排行等功能。
    """

    def __init__(self, db: DatabaseManager) -> None:
        """
        Args:
            db: 数据库管理器实例，用于读取职位记录。
        """
        self._db = db
        self._register_jieba_words()

    @staticmethod
    def _register_jieba_words() -> None:
        """将已知技能词加入 jieba 用户词典，提高分词准确率。"""
        for skill in _KNOWN_SKILLS:
            jieba.add_word(skill, freq=10000)
        for alias in SKILL_MAPPING:
            if len(alias) >= 2:
                jieba.add_word(alias, freq=5000)

    def _load_jobs(self) -> list[dict[str, Any]]:
        """从数据库加载全部职位字典列表。"""
        return self._db.get_all_jobs()

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """解析 ISO 格式或 datetime 对象。"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    def _normalize_skill(self, token: str) -> str | None:
        """
        将分词结果规范为标准技能名。

        Args:
            token: 原始词条。

        Returns:
            标准技能名；无法识别时返回 ``None``。
        """
        text = token.strip()
        if not text or text in _STOPWORDS:
            return None

        if text in _KNOWN_SKILLS:
            return text

        mapped = SKILL_MAPPING.get(text.lower())
        if mapped:
            return mapped

        # 英文技术词：仅保留词典中已知的技能，避免误识别碎片词
        if _SKILL_TOKEN_PATTERN.match(text) and len(text) >= 2:
            lower = text.lower()
            if lower in SKILL_MAPPING:
                return SKILL_MAPPING[lower]
            if text in _KNOWN_SKILLS:
                return text
            return None

        # 中文技能名：长度至少 2 且在已知集合中模糊包含
        if len(text) >= 2 and any(text in skill for skill in _KNOWN_SKILLS):
            for skill in _KNOWN_SKILLS:
                if text == skill or text in skill:
                    return skill

        return None

    def _tokenize(self, text: str) -> list[str]:
        """
        使用 jieba 对文本分词并过滤停用词。

        Args:
            text: 待分词文本。

        Returns:
            分词后的词条列表（未去重）。
        """
        if not text or not str(text).strip():
            return []

        tokens: list[str] = []
        for word in jieba.lcut(str(text)):
            word = word.strip()
            if len(word) < 2:
                continue
            if word in _STOPWORDS:
                continue
            if word.isdigit():
                continue
            tokens.append(word)
        return tokens

    def _extract_structured_skills(self, job: dict[str, Any]) -> list[str]:
        """
        从职位的 ``skills`` 字段提取标准技能列表。

        Args:
            job: 职位字典。

        Returns:
            去重后的标准技能名列表。
        """
        raw = job.get("skills")
        if not raw:
            return []

        items: list[str] = []
        if isinstance(raw, list):
            items = [str(s).strip() for s in raw if s]
        elif isinstance(raw, str):
            items = [p.strip() for p in re.split(r"[,，、;；|/]", raw) if p.strip()]

        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            skill = self._normalize_skill(item) or (
                item if item in _KNOWN_SKILLS else None
            )
            if skill and skill not in seen:
                seen.add(skill)
                result.append(skill)
        return result

    def _build_document(self, job: dict[str, Any]) -> str:
        """
        将职位标题、描述与技能合并为 TF-IDF 语料文档。

        Args:
            job: 职位字典。

        Returns:
            空格拼接的文本语料。
        """
        parts: list[str] = []
        title = job.get("title")
        description = job.get("description")
        skills = self._extract_structured_skills(job)

        if title:
            parts.append(str(title))
        if description:
            parts.append(str(description))
        if skills:
            parts.append(" ".join(skills))
        return " ".join(parts)

    def _get_job_skill_sets(self, jobs: list[dict[str, Any]]) -> list[set[str]]:
        """
        为每条职位构建技能集合（结构化字段 + 描述 TF-IDF 补充）。

        Args:
            jobs: 职位字典列表。

        Returns:
            每条职位对应的技能集合列表。
        """
        corpus = [self._build_document(job) for job in jobs]
        tfidf_skills_per_doc = self._extract_tfidf_skills_per_doc(corpus)

        skill_sets: list[set[str]] = []
        for job, tfidf_skills in zip(jobs, tfidf_skills_per_doc):
            skills = set(self._extract_structured_skills(job))
            skills.update(tfidf_skills)
            skill_sets.append(skills)
        return skill_sets

    def _extract_tfidf_skills_per_doc(
        self,
        corpus: list[str],
        top_k: int = 8,
    ) -> list[set[str]]:
        """
        对语料库逐文档提取 TF-IDF 权重最高的技能关键词。

        Args:
            corpus: 文档列表。
            top_k: 每篇文档保留的关键词数量上限。

        Returns:
            每篇文档对应的技能集合列表。
        """
        non_empty = [(i, doc) for i, doc in enumerate(corpus) if doc.strip()]
        if not non_empty:
            return [set() for _ in corpus]

        indices, docs = zip(*non_empty)

        def tokenizer(text: str) -> list[str]:
            return self._tokenize(text)

        vectorizer = TfidfVectorizer(
            tokenizer=tokenizer,
            token_pattern=None,
            lowercase=False,
            max_features=500,
            min_df=1,
        )

        try:
            matrix = vectorizer.fit_transform(docs)
        except ValueError:
            return [set() for _ in corpus]

        feature_names = vectorizer.get_feature_names_out()
        per_doc: list[set[str]] = [set() for _ in corpus]

        for row_idx, doc_idx in enumerate(indices):
            row = matrix.getrow(row_idx)
            if row.nnz == 0:
                continue

            pairs = sorted(
                zip(row.indices, row.data),
                key=lambda x: x[1],
                reverse=True,
            )
            skills: set[str] = set()
            for col, _score in pairs[: top_k * 3]:
                token = feature_names[col]
                skill = self._normalize_skill(token)
                if skill:
                    skills.add(skill)
                if len(skills) >= top_k:
                    break
            per_doc[doc_idx] = skills

        return per_doc

    def _compute_tfidf_global_scores(
        self,
        corpus: list[str],
    ) -> Counter[str]:
        """
        计算语料库全局 TF-IDF 技能加权得分。

        Args:
            corpus: 文档列表。

        Returns:
            技能 → 累计 TF-IDF 得分。
        """
        docs = [doc for doc in corpus if doc.strip()]
        if not docs:
            return Counter()

        def tokenizer(text: str) -> list[str]:
            return self._tokenize(text)

        vectorizer = TfidfVectorizer(
            tokenizer=tokenizer,
            token_pattern=None,
            lowercase=False,
            max_features=800,
            min_df=1,
        )

        try:
            matrix = vectorizer.fit_transform(docs)
        except ValueError:
            return Counter()

        scores: Counter[str] = Counter()
        feature_names = vectorizer.get_feature_names_out()

        for col in range(matrix.shape[1]):
            column_sum = matrix[:, col].sum()
            if column_sum <= 0:
                continue
            token = feature_names[col]
            skill = self._normalize_skill(token)
            if skill:
                scores[skill] += float(column_sum)

        return scores

    def get_skills_frequency(self, top_n: int = 100) -> Counter[str]:
        """
        统计技能出现频率（结构化标签计数 + TF-IDF 加权）。

        每条职位中的结构化 ``skills`` 字段计 1 次出现；
        同时对全文语料做 TF-IDF，将权重叠加到对应技能上。

        Args:
            top_n: 仅保留频率最高的前 N 个技能；``<=0`` 表示不截断。

        Returns:
            ``Counter``，键为技能名，值为综合频次/权重。
        """
        jobs = self._load_jobs()
        if not jobs:
            return Counter()

        frequency: Counter[str] = Counter()

        for job in jobs:
            for skill in self._extract_structured_skills(job):
                frequency[skill] += 1

        corpus = [self._build_document(job) for job in jobs]
        tfidf_scores = self._compute_tfidf_global_scores(corpus)
        for skill, score in tfidf_scores.items():
            frequency[skill] += max(1, int(round(score * 10)))

        if top_n > 0:
            return Counter(dict(frequency.most_common(top_n)))
        return frequency

    def get_skill_cooccurrence(self, top_n: int = 50) -> Counter[tuple[str, str]]:
        """
        统计技能两两共现次数。

        在同一职位记录中同时出现的技能对计为共现一次。

        Args:
            top_n: 仅返回共现频次最高的前 N 对；``<=0`` 表示不截断。

        Returns:
            ``Counter``，键为 ``(skill_a, skill_b)`` 有序元组（字典序），值为共现次数。
        """
        jobs = self._load_jobs()
        if not jobs:
            return Counter()

        skill_sets = self._get_job_skill_sets(jobs)
        cooccurrence: Counter[tuple[str, str]] = Counter()

        for skills in skill_sets:
            if len(skills) < 2:
                continue
            for a, b in combinations(sorted(skills), 2):
                cooccurrence[(a, b)] += 1

        if top_n > 0:
            return Counter(dict(cooccurrence.most_common(top_n)))
        return cooccurrence

    def analyze_skill_associations(
        self,
        min_support: float = 0.01,
        top_n: int = 30,
    ) -> list[dict[str, Any]]:
        """
        关联规则分析：挖掘技能之间的 support / confidence / lift。

        对每条职位的技能集合生成有序规则 ``A → B``（``A != B``），
        过滤支持度低于 ``min_support`` 的规则，按 ``lift`` 降序返回。

        Args:
            min_support: 最小支持度（技能对共现职位数 / 总职位数）。
            top_n: 返回规则条数上限。

        Returns:
            规则列表，每项包含 ``antecedent``, ``consequent``,
            ``support``, ``confidence``, ``lift``。
        """
        jobs = self._load_jobs()
        if not jobs:
            return []

        skill_sets = self._get_job_skill_sets(jobs)
        transactions = [s for s in skill_sets if s]
        n = len(transactions)
        if n == 0:
            return []

        item_count: Counter[str] = Counter()
        pair_count: Counter[tuple[str, str]] = Counter()

        for skills in transactions:
            for skill in skills:
                item_count[skill] += 1
            for a, b in combinations(skills, 2):
                pair_count[(a, b)] += 1
                pair_count[(b, a)] += 1

        rules: list[dict[str, Any]] = []

        for (antecedent, consequent), co_count in pair_count.items():
            if antecedent == consequent:
                continue

            support = co_count / n
            if support < min_support:
                continue

            antecedent_count = item_count[antecedent]
            consequent_count = item_count[consequent]
            if antecedent_count == 0 or consequent_count == 0:
                continue

            confidence = co_count / antecedent_count
            consequent_support = consequent_count / n
            lift = confidence / consequent_support if consequent_support > 0 else 0.0

            rules.append(
                {
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "support": round(support, 4),
                    "confidence": round(confidence, 4),
                    "lift": round(lift, 4),
                }
            )

        rules.sort(key=lambda r: (r["lift"], r["confidence"], r["support"]), reverse=True)

        if top_n > 0:
            return rules[:top_n]
        return rules

    def get_trending_skills(self, top_n: int = 20) -> list[dict[str, Any]]:
        """
        综合评分趋势技能排行。

        评分公式（可调权重）::
            score = recent_count * (1 + growth_rate) + tfidf_boost

        其中 ``growth_rate = (近期频次 - 前期频次) / (前期频次 + 1)``，
        ``tfidf_boost`` 为全局 TF-IDF 得分归一化后的加成。

        Args:
            top_n: 返回排行条数。

        Returns:
            按 ``score`` 降序排列的字典列表，含 ``skill``, ``score``,
            ``recent_count``, ``previous_count``, ``growth_rate``, ``total_count``。
        """
        jobs = self._load_jobs()
        if not jobs:
            return []

        now = datetime.now()
        recent_start = now - timedelta(days=_TREND_RECENT_DAYS)

        recent_counter: Counter[str] = Counter()
        previous_counter: Counter[str] = Counter()
        total_counter: Counter[str] = Counter()

        for job in jobs:
            skills = self._extract_structured_skills(job)
            if not skills:
                continue

            created = self._parse_datetime(job.get("created_at"))
            is_recent = created is not None and created >= recent_start

            for skill in skills:
                total_counter[skill] += 1
                if is_recent:
                    recent_counter[skill] += 1
                elif created is not None:
                    previous_counter[skill] += 1
                else:
                    previous_counter[skill] += 1

        corpus = [self._build_document(job) for job in jobs]
        tfidf_scores = self._compute_tfidf_global_scores(corpus)
        max_tfidf = max(tfidf_scores.values()) if tfidf_scores else 1.0

        rankings: list[dict[str, Any]] = []
        all_skills = set(total_counter) | set(tfidf_scores)

        for skill in all_skills:
            recent = recent_counter.get(skill, 0)
            previous = previous_counter.get(skill, 0)
            total = total_counter.get(skill, 0)
            growth_rate = (recent - previous) / (previous + 1)

            tfidf_boost = (tfidf_scores.get(skill, 0.0) / max_tfidf) * 5.0
            score = recent * (1.0 + growth_rate) + tfidf_boost

            if total == 0 and tfidf_scores.get(skill, 0) <= 0:
                continue

            rankings.append(
                {
                    "skill": skill,
                    "score": round(score, 4),
                    "recent_count": recent,
                    "previous_count": previous,
                    "growth_rate": round(growth_rate, 4),
                    "total_count": total,
                }
            )

        rankings.sort(
            key=lambda item: (item["score"], item["recent_count"], item["total_count"]),
            reverse=True,
        )

        if top_n > 0:
            return rankings[:top_n]
        return rankings


# 全局实例：项目内统一引用
skill_analyzer = SkillNLPAnalyzer(db_manager)
