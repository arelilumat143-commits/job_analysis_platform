# 职位CRUD接口
"""
提供职位相关的API接口：
- GET /api/jobs - 分页查询职位列表
- GET /api/jobs/{id} - 职位详情
- GET /api/jobs/search - 全文搜索
- GET /api/jobs/stats - 职位统计
- DELETE /api/jobs/{id} - 删除职位
"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException

from api.models import (
    BaseResponse, JobResponse, JobListResponse, JobStatsResponse, PaginationMeta
)
from api.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["职位管理"])
job_service = JobService()


@router.get("", response_model=BaseResponse)
async def get_jobs(
    city: Optional[str] = Query(None, description="城市筛选"),
    source: Optional[str] = Query(None, description="数据来源筛选"),
    industry: Optional[str] = Query(None, description="行业筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    experience: Optional[str] = Query(None, description="经验要求"),
    education: Optional[str] = Query(None, description="学历要求"),
    company_size: Optional[str] = Query(None, description="公司规模"),
    company_type: Optional[str] = Query(None, description="公司类型"),
    salary_min: Optional[float] = Query(None, description="最低薪资"),
    salary_max: Optional[float] = Query(None, description="最高薪资"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
) -> BaseResponse:
    """
    分页查询职位列表
    
    支持多条件筛选：城市、来源、行业、关键词、薪资范围等
    """
    result = job_service.get_jobs_paginated(
        city=city,
        source=source,
        industry=industry,
        keyword=keyword,
        experience=experience,
        education=education,
        company_size=company_size,
        company_type=company_type,
        salary_min=salary_min,
        salary_max=salary_max,
        page=page,
        page_size=page_size
    )
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/search", response_model=BaseResponse)
async def search_jobs(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
) -> BaseResponse:
    """
    全文搜索职位
    
    在职位名称、公司名称、职位描述中搜索
    """
    result = job_service.search_jobs(
        keyword=q,
        page=page,
        page_size=page_size
    )
    
    return BaseResponse(
        code=200,
        message="ok",
        data=result
    )


@router.get("/stats", response_model=BaseResponse)
async def get_job_stats() -> BaseResponse:
    """
    获取职位统计概览
    
    返回总数、按城市/行业/来源的统计
    """
    stats = job_service.get_job_stats()
    
    return BaseResponse(
        code=200,
        message="ok",
        data=stats
    )


@router.get("/distinct", response_model=BaseResponse)
async def get_distinct_values(
    field: str = Query(..., description="字段名(city/industry/source/experience/education)")
) -> BaseResponse:
    """
    获取指定字段的所有不重复值
    
    用于前端下拉选项
    """
    values = job_service.get_distinct_values(field)
    
    return BaseResponse(
        code=200,
        message="ok",
        data=values
    )


@router.get("/{job_id}", response_model=BaseResponse)
async def get_job_detail(job_id: int) -> BaseResponse:
    """
    获取职位详情
    """
    job = job_service.get_job_by_id(job_id)
    
    if job is None:
        raise HTTPException(status_code=404, detail="职位不存在")
    
    return BaseResponse(
        code=200,
        message="ok",
        data=job
    )


@router.delete("/{job_id}", response_model=BaseResponse)
async def delete_job(job_id: int) -> BaseResponse:
    """
    删除单条职位
    """
    success = job_service.delete_job(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="职位不存在或删除失败")
    
    return BaseResponse(
        code=200,
        message="删除成功",
        data={"id": job_id}
    )
