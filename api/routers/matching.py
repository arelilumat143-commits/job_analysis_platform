# ============================================================================
# 岗位匹配 API 路由
# POST /api/matching/jobs — 根据用户技能和期望匹配最合适的岗位
# ============================================================================
from fastapi import APIRouter

from api.services.matching_service import job_matching_service
from schemas.matching import JobMatchingRequest, JobMatchingResponse

router = APIRouter(prefix="/matching", tags=["岗位匹配"])


@router.post("/jobs", response_model=JobMatchingResponse)
async def match_jobs(request: JobMatchingRequest) -> JobMatchingResponse:
    """
    岗位智能匹配接口。

    根据用户的技能列表、期望城市、薪资范围，使用 TF-IDF + Cosine Similarity
    算法在已有岗位库中查找最匹配的岗位。

    匹配逻辑：
    - **技能匹配**（权重 50%）：TF-IDF 余弦相似度 + 核心技能加权 ×1.5
    - **城市匹配**（权重 20%）：精确城市匹配得分最高
    - **薪资匹配**（权重 30%）：检查期望薪资与岗位薪资的重叠度
    - **模糊匹配**：支持输入类别名（如 "前端"）自动展开为具体技术栈

    - **skills**: 用户技能列表（如 ["Python", "Django"]）
    - **city**: 期望城市（如 "北京"）
    - **salary_min**: 期望最低薪资（K/月），可选
    - **salary_max**: 期望最高薪资（K/月），可选
    - **top_n**: 返回前 N 个最佳匹配，默认 10
    """
    result = job_matching_service.match(
        skills=request.skills,
        city=request.city,
        salary_min=request.salary_min,
        salary_max=request.salary_max,
        top_n=request.top_n,
    )
    return JobMatchingResponse(**result)
