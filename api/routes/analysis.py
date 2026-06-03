# 数据分析接口
"""
提供数据分析相关的API接口：
- GET /api/analysis/salary - 薪资分析
- GET /api/analysis/city - 城市分析
- GET /api/analysis/skill - 技能分析
- GET /api/analysis/industry - 行业分析
"""

from typing import Optional
from fastapi import APIRouter, Query

from api.models import BaseResponse
from api.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["数据分析"])
analysis_service = AnalysisService()


@router.get("/salary", response_model=BaseResponse)
async def get_salary_analysis(
    city: Optional[str] = Query(None, description="城市筛选"),
    industry: Optional[str] = Query(None, description="行业筛选"),
    source: Optional[str] = Query(None, description="数据来源")
) -> BaseResponse:
    """
    薪资分析
    
    返回：
    - 基本统计（均值、中位数、最大最小值等）
    - 薪资分布
    - 按城市/行业/经验对比
    """
    result = analysis_service.analyze_salary(
        city=city,
        industry=industry,
        source=source
    )
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/city", response_model=BaseResponse)
async def get_city_analysis(
    limit: int = Query(20, ge=1, le=50, description="返回数量限制")
) -> BaseResponse:
    """
    城市分析
    
    返回：
    - 各城市职位数量
    - 各城市平均薪资
    - 各城市热门技能
    """
    result = analysis_service.analyze_cities(limit=limit)
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/skill", response_model=BaseResponse)
async def get_skill_analysis(
    limit: int = Query(50, ge=1, le=100, description="返回技能数量限制")
) -> BaseResponse:
    """
    技能分析
    
    返回：
    - 高频技能排行
    - 技能关联分析
    - 技能趋势
    """
    result = analysis_service.analyze_skills(limit=limit)
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/industry", response_model=BaseResponse)
async def get_industry_analysis(
    limit: int = Query(20, ge=1, le=50, description="返回数量限制")
) -> BaseResponse:
    """
    行业分析
    
    返回各行业的职位数量、平均薪资等信息
    """
    result = analysis_service.analyze_industries(limit=limit)
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/experience", response_model=BaseResponse)
async def get_experience_analysis() -> BaseResponse:
    """
    经验要求分析
    
    返回各经验要求的职位数量和薪资统计
    """
    result = analysis_service.analyze_experience()
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/education", response_model=BaseResponse)
async def get_education_analysis() -> BaseResponse:
    """
    学历要求分析
    
    返回各学历要求的职位数量和薪资统计
    """
    result = analysis_service.analyze_education()
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )
