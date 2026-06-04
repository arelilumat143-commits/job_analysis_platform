# ============================================================================
# 薪资预测 API 路由
# POST /api/prediction/salary — 单个职位薪资预测
# ============================================================================
from fastapi import APIRouter

from api.services.salary_predictor import salary_predict_service
from schemas.prediction import SalaryPredictRequest, SalaryPredictResponse

router = APIRouter(prefix="/prediction", tags=["薪资预测"])


@router.post("/salary", response_model=SalaryPredictResponse)
async def predict_salary(request: SalaryPredictRequest) -> SalaryPredictResponse:
    """
    薪资预测接口。

    根据城市、经验年限、技能列表、学历等信息，使用 XGBoost 模型预测
    该职位的薪资范围（min/avg/max），并返回置信度和影响因子。

    - **city**: 城市名称（如 "北京"、"上海"）
    - **experience_years**: 经验年限（如 3.0 表示3年）
    - **skills**: 技能列表（如 ["Python", "Django"]）
    - **education**: 最高学历（如 "本科"、"硕士"）
    - **industry**: 目标行业（可选）
    """
    result = salary_predict_service.predict(
        city=request.city,
        experience_years=request.experience_years,
        skills=request.skills,
        education=request.education,
        industry=request.industry,
    )
    return SalaryPredictResponse(**result)
