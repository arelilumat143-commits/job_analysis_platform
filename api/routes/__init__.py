# 路由模块
"""
API路由初始化
"""

from .jobs import router as jobs_router
from .analysis import router as analysis_router
from .ai import router as ai_router
from .crawler import router as crawler_router

__all__ = ['jobs_router', 'analysis_router', 'ai_router', 'crawler_router']
