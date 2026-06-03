# AI分析接口
"""
提供AI相关的API接口：
- POST /api/ai/predict-salary - 薪资预测
- GET /api/ai/clusters - 岗位聚类
- GET /api/ai/skill-trends - 技能趋势
"""

from fastapi import APIRouter

from api.models import (
    BaseResponse, SalaryPredictRequest, SalaryPredictResponse, ClusterResponse
)
from api.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI分析"])
ai_service = AIService()


@router.post("/predict-salary", response_model=BaseResponse)
async def predict_salary(request: SalaryPredictRequest) -> BaseResponse:
    """
    薪资预测
    
    根据城市、技能、学历、经验预测薪资范围
    
    - city: 城市
    - skills: 技能列表
    - education: 学历要求
    - experience: 经验要求
    """
    result = ai_service.predict_salary(
        city=request.city,
        skills=request.skills,
        education=request.education,
        experience=request.experience
    )
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/clusters", response_model=BaseResponse)
async def get_job_clusters(
    n_clusters: int = 5
) -> BaseResponse:
    """
    岗位聚类分析
    
    对职位进行聚类分析，发现相似职位群组
    
    - n_clusters: 聚类数量
    """
    result = ai_service.get_clusters(n_clusters=n_clusters)
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/skill-trends", response_model=BaseResponse)
async def get_skill_trends() -> BaseResponse:
    """
    技能趋势NLP分析
    
    分析技能的出现频率和关联趋势
    """
    result = ai_service.get_skill_trends()
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/salary-factors", response_model=BaseResponse)
async def get_salary_factors() -> BaseResponse:
    """
    薪资影响因素分析
    
    分析影响薪资的主要因素及权重
    """
    result = ai_service.get_salary_factors()
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )
