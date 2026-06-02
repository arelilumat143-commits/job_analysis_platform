"""
数据清洗模块。

将 ``jobs`` 表中的原始招聘数据标准化后写入 ``jobs_cleaned`` 表，
统一薪资单位（K/月）、城市名称、经验/学历枚举及技能标签等字段。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column

from storage.database import db_manager
from storage.models import Base, Job

# ---------------------------------------------------------------------------
# 标准化映射表
# ---------------------------------------------------------------------------

# 城市别名 → 标准城市名（不含「市」后缀）
CITY_MAPPING: dict[str, str] = {
    "北京": "北京",
    "北京市": "北京",
    "上海": "上海",
    "上海市": "上海",
    "广州": "广州",
    "广州市": "广州",
    "深圳": "深圳",
    "深圳市": "深圳",
    "杭州": "杭州",
    "杭州市": "杭州",
    "成都": "成都",
    "成都市": "成都",
    "武汉": "武汉",
    "武汉市": "武汉",
    "西安": "西安",
    "西安市": "西安",
    "南京": "南京",
    "南京市": "南京",
    "苏州": "苏州",
    "苏州市": "苏州",
    "重庆": "重庆",
    "重庆市": "重庆",
    "天津": "天津",
    "天津市": "天津",
    "沪": "上海",
    "深": "深圳",
    "杭": "杭州",
}

# 工作经验原文 → 标准档位
EXPERIENCE_MAPPING: dict[str, str] = {
    "不限": "不限",
    "无要求": "不限",
    "经验不限": "不限",
    "应届": "应届生",
    "应届生": "应届生",
    "应届毕业生": "应届生",
    "在校": "应届生",
    "实习": "应届生",
    "1年以内": "1年以内",
    "1年以下": "1年以内",
    "一年以内": "1年以内",
    "1-3年": "1-3年",
    "1～3年": "1-3年",
    "一到三年": "1-3年",
    "3-5年": "3-5年",
    "3～5年": "3-5年",
    "三到五年": "3-5年",
    "5-10年": "5-10年",
    "5～10年": "5-10年",
    "五到十年": "5-10年",
    "10年以上": "10年以上",
    "十年以上": "10年以上",
    "3年以上": "3-5年",
    "三年以上": "3-5年",
    "5年以上": "5-10年",
    "五年以上": "5-10年",
}

# 学历原文 → 标准档位
EDUCATION_MAPPING: dict[str, str] = {
    "不限": "不限",
    "学历不限": "不限",
    "无要求": "不限",
    "初中": "初中及以下",
    "初中及以下": "初中及以下",
    "高中": "高中",
    "中专": "中专/中技",
    "中技": "中专/中技",
    "中专/中技": "中专/中技",
    "大专": "大专",
    "专科": "大专",
    "高职": "大专",
    "本科": "本科",
    "大学本科": "本科",
    "统招本科": "本科",
    "全日制本科": "本科",
    "硕士": "硕士",
    "研究生": "硕士",
    "硕士研究生": "硕士",
    "博士": "博士",
    "博士研究生": "博士",
}

# 技能别名 → 标准写法（键为小写，匹配时不区分大小写）
SKILL_MAPPING: dict[str, str] = {
    "python": "Python",
    "py": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "go": "Go",
    "golang": "Go",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "redis": "Redis",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "linux": "Linux",
    "spark": "Spark",
    "hadoop": "Hadoop",
    "flink": "Flink",
    "hive": "Hive",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    "vue": "Vue",
    "vue.js": "Vue",
    "react": "React",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node": "Node.js",
    "aws": "AWS",
    "git": "Git",
    "机器学习": "机器学习",
    "深度学习": "深度学习",
    "nlp": "NLP",
    "cv": "计算机视觉",
}

# 薪资字符串解析用正则（按优先级排列）
_SALARY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 面议
    (re.compile(r"面议|薪资面议|待遇面议", re.I), "negotiable"),
    # 15-25K、15k~25k、15-25千/月
    (
        re.compile(
            r"(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*(?:k|K|千)(?:/月)?",
            re.I,
        ),
        "k_range",
    ),
    # 1.5-2.5万、15-25万/月
    (
        re.compile(
            r"(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*万(?:/月)?",
            re.I,
        ),
        "wan_month_range",
    ),
    # 15-25万/年
    (
        re.compile(
            r"(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*万/年",
            re.I,
        ),
        "wan_year_range",
    ),
    # 200-300/天、200-300元/天
    (
        re.compile(
            r"(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*(?:元)?/天",
            re.I,
        ),
        "daily_range",
    ),
    # 15K以上、20k起
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:k|K|千)(?:以上|起|\+)", re.I), "k_min"),
    # 1.5万以上
    (re.compile(r"(\d+(?:\.\d+)?)\s*万(?:以上|起|\+)", re.I), "wan_month_min"),
    # 单值 20K
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:k|K|千)(?:/月)?", re.I), "k_single"),
    # 单值 2万
    (re.compile(r"(\d+(?:\.\d+)?)\s*万(?:/月)?", re.I), "wan_month_single"),
]

# 每月计薪天数（日薪折算月薪）
_WORK_DAYS_PER_MONTH = 21.75


# ---------------------------------------------------------------------------
# 清洗后 ORM 模型
# ---------------------------------------------------------------------------


class JobCleaned(Base):
    """
    清洗后的职位信息表，对应 ``jobs_cleaned``。

    通过 ``source_job_id`` 关联原始 ``jobs`` 表记录，便于追溯与增量更新。
    """

    __tablename__ = "jobs_cleaned"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    district: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(50), nullable=True)
    education: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    __table_args__ = (
        Index("idx_cleaned_city_source", "city", "source"),
        Index("idx_cleaned_salary", "salary_min", "salary_max"),
    )

    def to_dict(self) -> dict[str, Any]:
        """将清洗后记录转为字典。"""
        return {
            "id": self.id,
            "source_job_id": self.source_job_id,
            "title": self.title,
            "company": self.company,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "city": self.city,
            "district": self.district,
            "experience": self.experience,
            "education": self.education,
            "skills": self.skills,
            "company_size": self.company_size,
            "company_type": self.company_type,
            "industry": self.industry,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "is_simulated": self.is_simulated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# 数据清洗器
# ---------------------------------------------------------------------------


class DataCleaner:
    """
    招聘数据清洗器。

    负责将原始字段转换为统一格式，并批量同步至 ``jobs_cleaned`` 表。
    """

    def _normalize_salary(
        self,
        raw_salary: str | dict[str, Any] | None,
    ) -> tuple[float | None, float | None]:
        """
        将多种薪资表述统一为 ``(salary_min, salary_max)``，单位 K/月。

        支持格式示例:
            - ``"15-25K"``、``"15k~25k"``
            - ``"1.5-2.5万"``、``"15-25万/年"``
            - ``"200-300/天"``
            - ``"面议"``
            - 字典中已有的 ``salary_min`` / ``salary_max`` 数值

        Args:
            raw_salary: 薪资字符串，或包含薪资字段的职位字典。

        Returns:
            薪资下限与上限（K/月）；面议或无法解析时均为 ``None``。
        """
        if isinstance(raw_salary, dict):
            text = raw_salary.get("salary") or raw_salary.get("salary_text")
            if text and str(text).strip():
                return self._parse_salary_string(str(text).strip())

            smin = self._to_float(raw_salary.get("salary_min"))
            smax = self._to_float(raw_salary.get("salary_max"))
            if smin is not None or smax is not None:
                if smin is not None and smax is not None and smin > smax:
                    smin, smax = smax, smin
                return smin, smax
            return None, None

        if raw_salary is None:
            return None, None

        if isinstance(raw_salary, (int, float)):
            value = float(raw_salary)
            return value, value

        text = str(raw_salary).strip()
        if not text:
            return None, None

        return self._parse_salary_string(text)

    def _parse_salary_string(self, text: str) -> tuple[float | None, float | None]:
        """解析薪资文本为 K/月区间。"""
        for pattern, kind in _SALARY_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue

            if kind == "negotiable":
                return None, None

            if kind in ("k_range", "wan_month_range", "wan_year_range", "daily_range"):
                low = float(match.group(1))
                high = float(match.group(2))
                return self._convert_range(low, high, kind)

            if kind == "k_min":
                low = float(match.group(1))
                return low, None

            if kind == "wan_month_min":
                low = float(match.group(1)) * 10
                return low, None

            if kind == "k_single":
                value = float(match.group(1))
                return value, value

            if kind == "wan_month_single":
                value = float(match.group(1)) * 10
                return value, value

        return None, None

    @staticmethod
    def _convert_range(
        low: float,
        high: float,
        kind: str,
    ) -> tuple[float, float]:
        """按单位将区间上下限转换为 K/月。"""
        if low > high:
            low, high = high, low

        if kind == "k_range":
            return round(low, 2), round(high, 2)

        if kind == "wan_month_range":
            return round(low * 10, 2), round(high * 10, 2)

        if kind == "wan_year_range":
            # 年薪（万）→ 月薪（K）：万/年 * 10 / 12
            return (
                round(low * 10 / 12, 2),
                round(high * 10 / 12, 2),
            )

        if kind == "daily_range":
            # 日薪（元）→ 月薪（K）：元/天 * 计薪天数 / 1000
            return (
                round(low * _WORK_DAYS_PER_MONTH / 1000, 2),
                round(high * _WORK_DAYS_PER_MONTH / 1000, 2),
            )

        return round(low, 2), round(high, 2)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """安全地将值转为浮点数。"""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _normalize_city(
        self,
        city: str | None,
        district: str | None = None,
    ) -> tuple[str | None, str | None]:
        """
        标准化城市与区域。

        处理规则:
            - 去除「市」后缀
            - 拆分 ``成都·高新区``、``上海-浦东新区`` 等形式
            - 应用 ``CITY_MAPPING`` 别名表

        Args:
            city: 原始城市字符串。
            district: 已有区域（可选），优先级低于从 city 中解析出的区域。

        Returns:
            ``(标准城市名, 区域)`` 元组。
        """
        if not city or not str(city).strip():
            return None, district

        raw = str(city).strip()
        parsed_district = district

        # 从复合地址中拆分城市与区域
        for sep in ("·", "•", "－", "-", "/", " "):
            if sep in raw:
                parts = [p.strip() for p in raw.split(sep, 1) if p.strip()]
                if len(parts) == 2:
                    raw, parsed_district = parts[0], parts[1]
                break

        raw = raw.replace("市", "").strip()
        normalized = CITY_MAPPING.get(raw, CITY_MAPPING.get(raw + "市", raw))

        if parsed_district:
            parsed_district = parsed_district.strip()
            # 区域名去掉常见前缀
            for prefix in ("市", "区", "县"):
                if parsed_district.endswith(prefix) and len(parsed_district) > 1:
                    pass  # 保留完整区名如「高新区」
            if parsed_district.endswith("市"):
                parsed_district = parsed_district.replace("市", "")

        return normalized or None, parsed_district

    def _normalize_experience(self, experience: str | None) -> str | None:
        """
        标准化工作经验要求。

        Args:
            experience: 原始经验描述。

        Returns:
            映射后的标准档位；空值返回 ``None``。
        """
        if not experience or not str(experience).strip():
            return None

        text = str(experience).strip()
        if text in EXPERIENCE_MAPPING:
            return EXPERIENCE_MAPPING[text]

        # 模糊匹配：去除空格后比对
        compact = text.replace(" ", "")
        for key, value in EXPERIENCE_MAPPING.items():
            if key.replace(" ", "") == compact:
                return value

        # 提取「N年以上」类模式
        if re.search(r"10\s*年", text):
            return "10年以上"
        if re.search(r"[5五]\s*年", text) and "以上" in text:
            return "5-10年"
        if re.search(r"[3三]\s*年", text) and "以上" in text:
            return "3-5年"

        return text

    def _normalize_education(self, education: str | None) -> str | None:
        """
        标准化学历要求。

        Args:
            education: 原始学历描述。

        Returns:
            映射后的标准档位；空值返回 ``None``。
        """
        if not education or not str(education).strip():
            return None

        text = str(education).strip()
        if text in EDUCATION_MAPPING:
            return EDUCATION_MAPPING[text]

        compact = text.replace(" ", "")
        for key, value in EDUCATION_MAPPING.items():
            if key.replace(" ", "") == compact:
                return value
            if key in text:
                return value

        return text

    def _normalize_skills(self, skills: list | str | None) -> list[str] | None:
        """
        标准化技能列表：拆分、映射别名、统一大小写并去重。

        Args:
            skills: JSON 列表或逗号/顿号分隔的字符串。

        Returns:
            去重后的标准技能列表；无有效技能时返回 ``None``。
        """
        if skills is None:
            return None

        items: list[str] = []
        if isinstance(skills, list):
            items = [str(s).strip() for s in skills if s and str(s).strip()]
        elif isinstance(skills, str):
            raw = skills.strip()
            if not raw:
                return None
            parts = re.split(r"[,，、;；|/]", raw)
            items = [p.strip() for p in parts if p.strip()]
        else:
            return None

        if not items:
            return None

        seen: set[str] = set()
        result: list[str] = []

        for item in items:
            key = item.lower()
            canonical = SKILL_MAPPING.get(key, item)
            # 未命中映射时，英文首字母大写风格（纯 ASCII 词）
            if canonical == item and item.isascii() and item.isalpha():
                canonical = item.capitalize()

            if canonical not in seen:
                seen.add(canonical)
                result.append(canonical)

        return result or None

    def clean_job(self, raw_job_dict: dict[str, Any]) -> dict[str, Any]:
        """
        清洗单条职位字典（不写入数据库）。

        Args:
            raw_job_dict: 来自 ``jobs`` 表的原始记录字典。

        Returns:
            适用于 ``JobCleaned`` 的字段字典（含 ``source_job_id``）。
        """
        salary_min, salary_max = self._normalize_salary(raw_job_dict)

        city, district = self._normalize_city(
            raw_job_dict.get("city"),
            raw_job_dict.get("district"),
        )

        title = (raw_job_dict.get("title") or "").strip()
        company = (raw_job_dict.get("company") or "").strip()
        source = (raw_job_dict.get("source") or "").strip()

        return {
            "source_job_id": raw_job_dict.get("id"),
            "title": title,
            "company": company,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "city": city or "未知",
            "district": district,
            "experience": self._normalize_experience(raw_job_dict.get("experience")),
            "education": self._normalize_education(raw_job_dict.get("education")),
            "skills": self._normalize_skills(raw_job_dict.get("skills")),
            "company_size": self._strip_or_none(raw_job_dict.get("company_size")),
            "company_type": self._strip_or_none(raw_job_dict.get("company_type")),
            "industry": self._strip_or_none(raw_job_dict.get("industry")),
            "description": self._strip_or_none(raw_job_dict.get("description")),
            "url": self._strip_or_none(raw_job_dict.get("url")),
            "source": source or "unknown",
            "is_simulated": bool(raw_job_dict.get("is_simulated")),
        }

    @staticmethod
    def _strip_or_none(value: Any) -> str | None:
        """去除首尾空白，空字符串转为 ``None``。"""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def clean_all(self) -> dict[str, int]:
        """
        从 ``jobs`` 表读取全部记录，清洗后写入 ``jobs_cleaned`` 表。

        已存在相同 ``source_job_id`` 的记录会被更新，否则插入新记录。

        Returns:
            统计信息 ``{"processed", "added", "updated"}``。
        """
        Base.metadata.create_all(db_manager.engine)

        raw_jobs = db_manager.get_all_jobs()
        added = 0
        updated = 0

        with db_manager.get_session() as session:
            for raw in raw_jobs:
                payload = self.clean_job(raw)
                source_job_id = payload.pop("source_job_id")

                if source_job_id is None:
                    continue

                existing = session.scalar(
                    select(JobCleaned).where(
                        JobCleaned.source_job_id == source_job_id
                    )
                )

                if existing is None:
                    session.add(
                        JobCleaned(source_job_id=source_job_id, **payload)
                    )
                    added += 1
                else:
                    for key, value in payload.items():
                        setattr(existing, key, value)
                    existing.updated_at = datetime.now()
                    updated += 1

            session.flush()

        return {
            "processed": len(raw_jobs),
            "added": added,
            "updated": updated,
        }


# 模块级便捷实例
data_cleaner = DataCleaner()
