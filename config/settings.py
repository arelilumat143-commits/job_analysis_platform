# 城市招聘市场智能分析平台
"""
配置文件 - 集中管理所有配置项
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库配置
class DatabaseConfig:
    """数据库配置"""
    # 默认使用MySQL（生产环境）
    DB_TYPE = os.getenv('DB_TYPE', 'mysql')  # sqlite / mysql
    
    # SQLite配置
    SQLITE_PATH = BASE_DIR / 'data' / 'jobs.db'
    SQLITE_URL = f'sqlite:///{SQLITE_PATH}'
    
    # MySQL配置（预留，方便后续切换）
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3307))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '123456')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'job_analysis')
    MYSQL_URL = f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}'
    
    @property
    def url(self):
        """获取当前数据库URL"""
        if self.DB_TYPE == 'mysql':
            return self.MYSQL_URL
        return self.SQLITE_URL

# Redis配置
class RedisConfig:
    """Redis配置（预留）"""
    REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'false').lower() == 'true'
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
    
    # 缓存配置
    CACHE_TTL = 3600  # 缓存过期时间（秒）
    CACHE_MAX_SIZE = 1000  # 最大缓存条数

# 爬虫配置
class CrawlerConfig:
    """爬虫配置"""
    # 请求间隔（秒）
    REQUEST_INTERVAL_MIN = 2.0
    REQUEST_INTERVAL_MAX = 5.0
    
    # 请求超时（秒）
    REQUEST_TIMEOUT = 30
    
    # 重试次数
    MAX_RETRIES = 3
    
    # User-Agent列表
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    # 爬虫开关
    BOSS_ENABLED = True
    ZHILIAN_ENABLED = True
    QIANCHENG_ENABLED = True

# Streamlit配置
class StreamlitConfig:
    """Streamlit Web配置"""
    PAGE_TITLE = "城市招聘市场智能分析平台"
    PAGE_ICON = "📊"
    LAYOUT = "wide"
    INITIAL_SIDEBAR_STATE = "expanded"
    
    # 主题颜色
    PRIMARY_COLOR = "#1f77b4"
    SECONDARY_COLOR = "#ff7f0e"
    SUCCESS_COLOR = "#2ca02c"
    WARNING_COLOR = "#d62728"

# 路径配置
class PathConfig:
    """路径配置"""
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / 'data'
    LOG_DIR = BASE_DIR / 'logs'
    EXPORT_DIR = BASE_DIR / 'exports'
    
    # 确保目录存在
    @staticmethod
    def ensure_dirs():
        """确保必要目录存在"""
        PathConfig.DATA_DIR.mkdir(parents=True, exist_ok=True)
        PathConfig.LOG_DIR.mkdir(parents=True, exist_ok=True)
        PathConfig.EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# 主配置类
class Settings:
    """配置管理单例类"""
    def __init__(self):
        self.database = DatabaseConfig()
        self.redis = RedisConfig()
        self.crawler = CrawlerConfig()
        self.streamlit = StreamlitConfig()
        self.path = PathConfig()
        
        # 确保目录存在
        self.path.ensure_dirs()
    
    def get_db_url(self):
        """获取数据库URL"""
        return self.database.url

# 创建全局配置实例
settings = Settings()
