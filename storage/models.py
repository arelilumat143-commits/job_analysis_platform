"""
SQLAlchemy ORM 数据模型定义。

本模块定义职位信息表 ``jobs`` 及其字段、索引，供 storage 层持久化与查询使用。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------------------------
# ORM 基类
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """声明式 ORM 基类，所有模型均继承此类。"""


# ---------------------------------------------------------------------------
# 职位信息表
# ---------------------------------------------------------------------------


class Job(Base):
    """
    职位信息 ORM 模型，对应数据库表 ``jobs``。

    存储从各招聘渠道采集或模拟生成的职位数据，支持按城市、来源、薪资等维度检索。
    """

    __tablename__ = "jobs"

    # 主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 职位基本信息
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # 薪资范围（单位：K/月），可为空表示未披露
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 地理位置
    city: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    district: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 任职要求
    experience: Mapped[str | None] = mapped_column(String(50), nullable=True)
    education: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # 公司属性
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # 职位详情与来源
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # 是否为模拟数据（用于演示或测试）
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 时间戳
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

    # 复合索引：加速「城市 + 来源」与「薪资区间」类查询
    __table_args__ = (
        Index("idx_city_source", "city", "source"),
        Index("idx_salary", "salary_min", "salary_max"),
    )

    def to_dict(self) -> dict[str, Any]:
        """
        将模型实例转换为普通字典，便于 JSON 序列化或 API 返回。

        Returns:
            包含全部字段的字典；``DateTime`` 字段转为 ISO 8601 字符串。
        """
        return {
            "id": self.id,
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

    def __repr__(self) -> str:
        return (
            f"<Job(id={self.id!r}, title={self.title!r}, "
            f"company={self.company!r}, city={self.city!r})>"
        )
