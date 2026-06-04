# 路由模块
"""
API路由初始化
"""

from .jobs import router as jobs_router
from .analysis import router as analysis_router
from .ai import router as ai_router
from .crawler import router as crawler_router
from api.routers.prediction import router as prediction_router
from api.routers.matching import router as matching_router

__all__ = [
    'jobs_router', 'analysis_router', 'ai_router', 'crawler_router',
    'prediction_router', 'matching_router',
]
