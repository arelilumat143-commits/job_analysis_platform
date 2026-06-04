# ============================================================================
# 薪资预测 Schema — 请求/响应数据结构
# ============================================================================
from typing import List, Optional
from pydantic import BaseModel, Field


class SalaryPredictRequest(BaseModel):
    """薪资预测请求"""
    city: str = Field(..., description="城市名称，如 北京、上海、深圳", examples=["北京"], min_length=1, max_length=50)
    experience_years: float = Field(
        ..., description="经验年限（数值），如 1.5 表示1年半", ge=0.0, le=50.0, examples=[3.0]
    )
    skills: List[str] = Field(
        ..., description="技能列表，如 ['Python', 'Django', 'MySQL']",
        examples=[["Python", "Django", "MySQL", "Redis"]], min_length=1, max_length=50
    )
    education: str = Field(
        ..., description="最高学历",
        examples=["本科"], min_length=1, max_length=20
    )
    industry: Optional[str] = Field(
        None, description="目标行业（可选），如 互联网、金融",
        examples=["互联网"], max_length=50
    )


class SalaryBreakdown(BaseModel):
    """薪资拆分预测"""
    salary_min: float = Field(description="预测薪资下限（K/月）")
    salary_avg: float = Field(description="预测薪资中位值（K/月）")
    salary_max: float = Field(description="预测薪资上限（K/月）")


class FactorItem(BaseModel):
    """影响因子（用于可解释性）"""
    factor: str = Field(description="影响因子名称，如 城市:北京、技能:Python")
    impact: float = Field(description="影响值，正数表示推高薪资，负数表示降低")
    explanation: str = Field(description="人类可读的解释说明")


class SalaryPredictResponse(BaseModel):
    """薪资预测响应"""
    prediction: SalaryBreakdown = Field(description="薪资预测结果")
    confidence: float = Field(
        description="预测置信度 0-1，基于训练数据相似度估算", ge=0.0, le=1.0, default=0.75
    )
    factors: List[FactorItem] = Field(
        default_factory=list, description="影响因子列表（按重要性降序）"
    )
    model_version: str = Field(default="v2.0", description="模型版本号")
