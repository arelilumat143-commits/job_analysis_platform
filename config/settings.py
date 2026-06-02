"""
项目全局配置模块。

本模块集中管理路径、数据库等运行时配置，供 crawler、storage、api 等子模块统一引用。
推荐通过 ``from config.settings import settings`` 访问配置，避免在各处硬编码路径。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

# 项目根目录：当前文件位于 config/ 下，因此向上两级即为项目根
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# SQLite 默认数据库文件路径
DEFAULT_SQLITE_PATH: Path = BASE_DIR / "data" / "jobs.db"

# 支持的数据库后端类型
DatabaseBackend = Literal["sqlite", "mysql"]


# ---------------------------------------------------------------------------
# 数据库配置
# ---------------------------------------------------------------------------


@dataclass
class DatabaseConfig:
    """
    数据库连接配置。

    Attributes:
        backend: 数据库类型，``"sqlite"`` 或 ``"mysql"``，默认 SQLite。
        sqlite_path: SQLite 数据库文件路径，仅在 backend 为 sqlite 时使用。
        mysql_host: MySQL 主机地址。
        mysql_port: MySQL 端口。
        mysql_user: MySQL 用户名。
        mysql_password: MySQL 密码。
        mysql_database: MySQL 数据库名。
    """

    backend: DatabaseBackend = "mysql"
    sqlite_path: Path = field(default_factory=lambda: DEFAULT_SQLITE_PATH)

    # MySQL 相关参数（backend="mysql" 时生效）
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3307
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_database: str = "job_analysis"

    @property
    def url(self) -> str:
        """
        生成 SQLAlchemy 兼容的数据库连接 URL。

        Returns:
            - SQLite: ``sqlite:////absolute/path/to/jobs.db``
            - MySQL:  ``mysql+pymysql://user:pass@host:port/database``

        Raises:
            ValueError: 当 backend 不是支持的类型时抛出。
        """
        if self.backend == "sqlite":
            # as_posix() 保证跨平台路径格式；resolve() 转为绝对路径
            db_file = self.sqlite_path.resolve().as_posix()
            return f"sqlite:///{db_file}"

        if self.backend == "mysql":
            return (
                f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
                f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            )

        raise ValueError(f"不支持的数据库类型: {self.backend!r}")


# ---------------------------------------------------------------------------
# 应用级配置
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    """
    应用全局设置容器。

    可通过环境变量覆盖部分配置，便于本地开发与生产部署切换。
    """

    debug: bool = False
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    @classmethod
    def from_env(cls) -> Settings:
        """
        从环境变量构建配置实例。

        支持的环境变量:
            APP_DEBUG          - 是否开启调试模式（"1"/"true" 为真）
            DB_BACKEND         - 数据库类型: sqlite | mysql
            DB_SQLITE_PATH     - SQLite 文件路径（可选）
            MYSQL_HOST         - MySQL 主机
            MYSQL_PORT         - MySQL 端口
            MYSQL_USER         - MySQL 用户名
            MYSQL_PASSWORD     - MySQL 密码
            MYSQL_DATABASE     - MySQL 数据库名
        """
        backend = os.getenv("DB_BACKEND", "sqlite").lower()
        if backend not in ("sqlite", "mysql"):
            raise ValueError(
                f"DB_BACKEND 必须是 'sqlite' 或 'mysql'，当前值: {backend!r}"
            )

        sqlite_path = Path(
            os.getenv("DB_SQLITE_PATH", str(DEFAULT_SQLITE_PATH))
        )

        database = DatabaseConfig(
            backend=backend,  # type: ignore[arg-type]
            sqlite_path=sqlite_path,
            mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
            mysql_user=os.getenv("MYSQL_USER", "root"),
            mysql_password=os.getenv("MYSQL_PASSWORD", ""),
            mysql_database=os.getenv("MYSQL_DATABASE", "jobs"),
        )

        debug_raw = os.getenv("APP_DEBUG", "").lower()
        debug = debug_raw in ("1", "true", "yes")

        return cls(debug=debug, database=database)


# 全局单例：项目内统一引用此实例
settings: Settings = Settings()
