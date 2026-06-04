# ============================================================================
# 岗位匹配 Schema — 请求/响应数据结构
# ============================================================================
from typing import List, Optional
from pydantic import BaseModel, Field


class JobMatchingRequest(BaseModel):
    """岗位匹配请求"""
    skills: List[str] = Field(
        ..., description="用户技能列表", examples=[["Python", "Django", "MySQL"]],
        min_length=1, max_length=50
    )
    city: str = Field(
        ..., description="期望城市", examples=["北京"], min_length=1, max_length=50
    )
    salary_min: Optional[float] = Field(
        None, description="期望最低薪资（K/月），留空表示不限制", ge=0.0, examples=[15.0]
    )
    salary_max: Optional[float] = Field(
        None, description="期望最高薪资（K/月），留空表示不限制", ge=0.0, examples=[30.0]
    )
    top_n: int = Field(
        default=10, description="返回前 N 个最匹配的岗位", ge=1, le=50
    )


class MatchReason(BaseModel):
    """匹配理由"""
    skill_match: List[str] = Field(
        default_factory=list, description="匹配的技能列表"
    )
    skill_coverage: float = Field(
        default=0.0, description="技能覆盖率 0-1"
    )
    city_match: bool = Field(
        default=False, description="城市是否完全匹配"
    )
    salary_match: bool = Field(
        default=False, description="薪资是否在期望范围内"
    )


class MatchedJob(BaseModel):
    """匹配到的岗位"""
    job_id: int = Field(description="岗位 ID")
    title: str = Field(description="职位名称")
    company: str = Field(description="公司名称")
    city: str = Field(description="城市")
    salary_min: Optional[float] = Field(None, description="最低薪资（K/月）")
    salary_max: Optional[float] = Field(None, description="最高薪资（K/月）")
    required_skills: List[str] = Field(default_factory=list, description="岗位要求技能")
    score: float = Field(description="综合匹配分数 0-100")
    reasons: MatchReason = Field(description="匹配理由详情")


class JobMatchingResponse(BaseModel):
    """岗位匹配响应"""
    total_jobs_scanned: int = Field(description="扫描的岗位总数")
    matched_count: int = Field(description="匹配到的岗位数量")
    top_matches: List[MatchedJob] = Field(description="Top N 匹配岗位")
    user_skills: List[str] = Field(description="用户输入的技能（标准化后）")
