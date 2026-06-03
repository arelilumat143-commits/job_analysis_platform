# Pydantic数据模型 - 请求/响应schema定义
"""
定义所有API的请求参数和响应数据结构
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """统一响应基类"""
    code: int = Field(default=200, description="状态码，200表示成功")
    message: str = Field(default="ok", description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")


class PaginationMeta(BaseModel):
    """分页元信息"""
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")


class JobBase(BaseModel):
    """职位基本信息"""
    title: str = Field(description="职位名称")
    company: str = Field(description="公司名称")
    city: str = Field(description="城市")
    source: str = Field(description="数据来源")


class JobResponse(JobBase):
    """职位响应数据"""
    id: int = Field(description="职位ID")
    salary_min: Optional[float] = Field(None, description="最低薪资(K/月)")
    salary_max: Optional[float] = Field(None, description="最高薪资(K/月)")
    experience: Optional[str] = Field(None, description="经验要求")
    education: Optional[str] = Field(None, description="学历要求")
    skills: Optional[List[str]] = Field(None, description="技能要求")
    company_size: Optional[str] = Field(None, description="公司规模")
    company_type: Optional[str] = Field(None, description="公司类型")
    industry: Optional[str] = Field(None, description="行业")
    description: Optional[str] = Field(None, description="职位描述")
    url: Optional[str] = Field(None, description="原始URL")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class JobListResponse(BaseModel):
    """职位列表响应"""
    items: List[JobResponse] = Field(description="职位列表")
    pagination: PaginationMeta = Field(description="分页信息")


class JobStatsResponse(BaseModel):
    """职位统计响应"""
    total: int = Field(description="职位总数")
    by_city: List[Dict[str, Any]] = Field(description="按城市统计")
    by_industry: List[Dict[str, Any]] = Field(description="按行业统计")
    by_source: List[Dict[str, Any]] = Field(description="按来源统计")


class SalaryAnalysisResponse(BaseModel):
    """薪资分析响应"""
    basic_stats: Dict[str, Any] = Field(description="基本统计")
    distribution: List[Dict[str, Any]] = Field(description="薪资分布")
    by_city: List[Dict[str, Any]] = Field(description="按城市对比")
    by_industry: List[Dict[str, Any]] = Field(description="按行业对比")
    by_experience: List[Dict[str, Any]] = Field(description="按经验对比")


class CityAnalysisResponse(BaseModel):
    """城市分析响应"""
    job_counts: List[Dict[str, Any]] = Field(description="各城市职位数")
    avg_salary: List[Dict[str, Any]] = Field(description="各城市平均薪资")
    top_skills: List[Dict[str, Any]] = Field(description="热门技能")


class SkillAnalysisResponse(BaseModel):
    """技能分析响应"""
    top_skills: List[Dict[str, Any]] = Field(description="高频技能")
    skill_correlations: List[Dict[str, Any]] = Field(description="技能关联")
    skill_trends: List[Dict[str, Any]] = Field(description="技能趋势")


class IndustryAnalysisResponse(BaseModel):
    """行业分析响应"""
    industries: List[Dict[str, Any]] = Field(description="各行业统计")


class SalaryPredictRequest(BaseModel):
    """薪资预测请求"""
    city: str = Field(description="城市")
    skills: List[str] = Field(description="技能列表")
    education: str = Field(description="学历要求")
    experience: str = Field(description="经验要求")


class SalaryPredictResponse(BaseModel):
    """薪资预测响应"""
    predicted_salary_min: float = Field(description="预测最低薪资")
    predicted_salary_max: float = Field(description="预测最高薪资")
    confidence: float = Field(description="预测置信度")
    model_version: str = Field(description="模型版本")


class ClusterResponse(BaseModel):
    """聚类分析响应"""
    clusters: List[Dict[str, Any]] = Field(description="聚类结果")
    cluster_count: int = Field(description="聚类数量")


class CrawlerStartRequest(BaseModel):
    """爬虫启动请求"""
    source: str = Field(description="数据源(boss/zhilian/qiancheng/shixiseng)")
    city: Optional[str] = Field(None, description="城市")
    keyword: Optional[str] = Field(None, description="关键词")


class CrawlerStartResponse(BaseModel):
    """爬虫启动响应"""
    task_id: str = Field(description="任务ID")
    status: str = Field(description="任务状态")
    message: str = Field(description="提示信息")


class CrawlerStatusResponse(BaseModel):
    """爬虫状态响应"""
    status: str = Field(description="爬虫状态")
    total_collected: int = Field(description="已采集数量")
    running_tasks: List[Dict[str, Any]] = Field(description="运行中的任务")


class DataSourceResponse(BaseModel):
    """数据源信息"""
    name: str = Field(description="数据源名称")
    code: str = Field(description="数据源代码")
    enabled: bool = Field(description="是否启用")
    description: str = Field(description="描述")
