# 城市招聘市场智能分析平台
"""
配置文件模块
负责所有配置项的集中管理
"""

from .settings import Settings

# 导出Settings单例实例
settings = Settings()

__all__ = ['settings', 'Settings']
