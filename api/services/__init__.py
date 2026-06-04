# 服务层模块
"""
服务层初始化
"""

from .job_service import JobService
from .analysis_service import AnalysisService
from .ai_service import AIService
from .crawler_service import CrawlerService
from .salary_predictor import SalaryPredictService, salary_predict_service
from .matching_service import JobMatchingService, job_matching_service

__all__ = [
    'JobService', 'AnalysisService', 'AIService', 'CrawlerService',
    'SalaryPredictService', 'salary_predict_service',
    'JobMatchingService', 'job_matching_service',
]
