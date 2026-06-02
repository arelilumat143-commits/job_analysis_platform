"""
数据库连接与会话管理模块。

提供单例 ``DatabaseManager``，封装 Engine / Session 创建及职位数据的增删查操作。
推荐通过 ``from storage.database import db_manager`` 访问全局实例。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import settings
from storage.models import Base, Job

# Job 模型允许通过字典写入的字段（不含自增主键与时间戳，由 ORM 默认填充）
_JOB_FIELDS = frozenset(
    {
        "title",
        "company",
        "salary_min",
        "salary_max",
        "city",
        "district",
        "experience",
        "education",
        "skills",
        "company_size",
        "company_type",
        "industry",
        "description",
        "url",
        "source",
        "is_simulated",
    }
)


# ---------------------------------------------------------------------------
# 数据库管理器（单例）
# ---------------------------------------------------------------------------


class DatabaseManager:
    """
    数据库管理器，负责 Engine 生命周期与 CRUD 封装。

    采用单例模式，保证全局仅存在一个连接池实例，避免重复创建 Engine。
    """

    _instance: DatabaseManager | None = None

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        # 单例只初始化一次
        if self._initialized:
            return

        self._engine: Engine = self._create_engine()
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        self._ensure_tables()
        self._initialized = True

    def _create_engine(self) -> Engine:
        """
        根据配置创建 SQLAlchemy Engine。

        SQLite 使用 ``StaticPool`` 与 ``check_same_thread=False``，
        以支持多线程 / 异步场景下的连接复用。
        """
        url = settings.database.url
        echo = settings.debug

        if settings.database.backend == "sqlite":
            # 确保 SQLite 文件所在目录存在
            settings.database.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

            return create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=echo,
            )

        return create_engine(url, echo=echo)

    def _ensure_tables(self) -> None:
        """若表不存在则自动建表。"""
        Base.metadata.create_all(self._engine)

    @property
    def engine(self) -> Engine:
        """暴露底层 Engine，供迁移脚本或原生 SQL 使用。"""
        return self._engine

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        获取数据库会话的上下文管理器。

        正常结束时自动 ``commit``，异常时 ``rollback`` 并向上抛出。

        Yields:
            活跃的 ``Session`` 实例。

        Example:
            with db_manager.get_session() as session:
                session.add(job)
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _build_job(job_data: dict[str, Any]) -> Job:
        """
        从字典构造 ``Job`` 实例，忽略未知字段。

        Args:
            job_data: 职位字段字典，键名需与模型属性一致。

        Returns:
            未持久化的 ``Job`` 对象。
        """
        payload = {k: v for k, v in job_data.items() if k in _JOB_FIELDS}
        return Job(**payload)

    @staticmethod
    def _apply_filters(
        stmt: Any,
        *,
        city: str | None = None,
        source: str | None = None,
        company: str | None = None,
        industry: str | None = None,
        title_keyword: str | None = None,
        min_salary: float | None = None,
        max_salary: float | None = None,
        is_simulated: bool | None = None,
    ) -> Any:
        """
        为查询语句追加可选过滤条件。

        Args:
            stmt: SQLAlchemy ``select`` 语句。
            city: 精确匹配城市。
            source: 精确匹配数据来源。
            company: 公司名称模糊匹配（包含）。
            industry: 精确匹配行业。
            title_keyword: 职位名称模糊匹配（包含）。
            min_salary: 期望最低薪资（K/月），筛选 ``salary_max >= min_salary`` 的职位。
            max_salary: 期望最高薪资（K/月），筛选 ``salary_min <= max_salary`` 的职位。
            is_simulated: 是否仅查询模拟数据。

        Returns:
            附加了 ``where`` 子句的查询语句。
        """
        if city is not None:
            stmt = stmt.where(Job.city == city)
        if source is not None:
            stmt = stmt.where(Job.source == source)
        if company is not None:
            stmt = stmt.where(Job.company.contains(company))
        if industry is not None:
            stmt = stmt.where(Job.industry == industry)
        if title_keyword is not None:
            stmt = stmt.where(Job.title.contains(title_keyword))
        if min_salary is not None:
            stmt = stmt.where(Job.salary_max >= min_salary)
        if max_salary is not None:
            stmt = stmt.where(Job.salary_min <= max_salary)
        if is_simulated is not None:
            stmt = stmt.where(Job.is_simulated == is_simulated)
        return stmt

    def add_job(self, job_data: dict[str, Any]) -> int | None:
        """
        新增单条职位记录。

        若 ``url`` 非空且库中已存在相同 URL，则跳过插入（去重）。

        Args:
            job_data: 职位字段字典。

        Returns:
            新记录的主键 ``id``；因 URL 重复被跳过时返回 ``None``。
        """
        with self.get_session() as session:
            url = job_data.get("url")
            if url:
                existing = session.scalar(
                    select(Job.id).where(Job.url == url).limit(1)
                )
                if existing is not None:
                    return None

            job = self._build_job(job_data)
            session.add(job)
            session.flush()
            return job.id

    def add_jobs_batch(self, jobs_data: list[dict[str, Any]]) -> dict[str, int]:
        """
        批量新增职位记录，逐条进行 URL 去重。

        Args:
            jobs_data: 职位字典列表。

        Returns:
            统计结果 ``{"added": 成功条数, "skipped": 跳过条数}``。
        """
        added = 0
        skipped = 0

        with self.get_session() as session:
            for job_data in jobs_data:
                url = job_data.get("url")
                if url:
                    existing = session.scalar(
                        select(Job.id).where(Job.url == url).limit(1)
                    )
                    if existing is not None:
                        skipped += 1
                        continue

                session.add(self._build_job(job_data))
                # flush 使同批次内后续记录能检测到刚插入的 URL
                session.flush()
                added += 1

        return {"added": added, "skipped": skipped}

    def get_all_jobs(self) -> list[dict[str, Any]]:
        """
        查询全部职位记录。

        必须在 Session 仍活跃时调用 ``to_dict()``，避免延迟加载导致的数据失效。

        Returns:
            职位字典列表，按 ``id`` 升序排列。
        """
        with self.get_session() as session:
            jobs = session.scalars(select(Job).order_by(Job.id)).all()
            return [job.to_dict() for job in jobs]

    def get_jobs(
        self,
        *,
        city: str | None = None,
        source: str | None = None,
        company: str | None = None,
        industry: str | None = None,
        title_keyword: str | None = None,
        min_salary: float | None = None,
        max_salary: float | None = None,
        is_simulated: bool | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        按多条件过滤查询职位记录。

        所有过滤参数均为可选，不传则不作为筛选条件。
        同样在 Session 内完成 ``to_dict()`` 转换。

        Args:
            city: 城市（精确匹配）。
            source: 数据来源（精确匹配）。
            company: 公司名称（模糊匹配）。
            industry: 行业（精确匹配）。
            title_keyword: 职位名称关键词（模糊匹配）。
            min_salary: 最低期望薪资（K/月）。
            max_salary: 最高期望薪资（K/月）。
            is_simulated: 是否模拟数据。
            limit: 返回条数上限，``None`` 表示不限制。
            offset: 分页偏移量，默认 0。

        Returns:
            符合条件的职位字典列表，按 ``id`` 升序排列。
        """
        with self.get_session() as session:
            stmt = select(Job).order_by(Job.id)
            stmt = self._apply_filters(
                stmt,
                city=city,
                source=source,
                company=company,
                industry=industry,
                title_keyword=title_keyword,
                min_salary=min_salary,
                max_salary=max_salary,
                is_simulated=is_simulated,
            )
            if offset:
                stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            jobs = session.scalars(stmt).all()
            return [job.to_dict() for job in jobs]


# 全局单例：项目内统一引用此实例
db_manager = DatabaseManager()
