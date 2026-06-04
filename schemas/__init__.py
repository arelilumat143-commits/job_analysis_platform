# Pydantic Schema 模块
from .prediction import SalaryPredictRequest, SalaryPredictResponse, SalaryBreakdown, FactorItem
from .matching import JobMatchingRequest, JobMatchingResponse, MatchedJob, MatchReason

__all__ = [
    'SalaryPredictRequest', 'SalaryPredictResponse', 'SalaryBreakdown', 'FactorItem',
    'JobMatchingRequest', 'JobMatchingResponse', 'MatchedJob', 'MatchReason',
]
