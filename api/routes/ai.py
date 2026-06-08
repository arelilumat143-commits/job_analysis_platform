# AI分析接口
"""
提供AI相关的API接口：
- POST /api/ai/predict-salary - 薪资预测
- GET /api/ai/clusters - 岗位聚类
- GET /api/ai/skill-trends - 技能趋势
"""

from fastapi import APIRouter

from api.models import (
    BaseResponse, SalaryPredictRequest, SalaryPredictResponse, ClusterResponse,
    AIChatRequest,
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


# ---- AI 大模型对话 ----

# 对话系统提示词（含市场数据上下文）
_CHAT_SYSTEM_PROMPT = """你是一个专业的招聘市场分析助手，名为"招聘AI助手"。你可以访问平台上的 22,000+ 条真实招聘数据，为用户解答关于求职、招聘市场、薪资、技能需求等方面的问题。

你的能力包括：
- 分析不同城市的就业市场和薪资水平
- 解读热门技能和技术趋势
- 提供职业发展建议
- 对比不同岗位的薪资待遇
- 分析学历和经验对薪资的影响

回答要求：
1. 使用中文，语气专业且友好
2. 基于提供的数据给出具体分析，而非泛泛而谈
3. 适当使用数据和百分比佐证观点
4. 回答简洁，控制在 200-500 字（除非用户要求详细分析）
5. 如果用户的问题超出数据范围，基于你的专业知识给出合理建议
6. 使用 Markdown 格式，适当使用标题和列表"""


def _build_context_prompt() -> str:
    """从数据库动态构建市场数据上下文，注入系统提示"""
    try:
        from api.services.analysis_service import AnalysisService
        svc = AnalysisService()

        # 获取市场洞察数据
        insight = svc.get_market_insight()
        if not insight:
            return ""

        ai_summary = insight.get("ai_summary", "")
        key_findings = insight.get("key_findings", [])
        top_jobs = insight.get("top_jobs", [])[:5]
        top_cities = insight.get("top_cities", [])[:5]
        salary_info = insight.get("salary_overview", {})
        health = insight.get("market_health", {})

        ctx = "## 当前平台数据概览\n\n"
        ctx += f"平台共收录 22,908 条真实招聘数据，覆盖主要城市。\n\n"

        if ai_summary:
            ctx += f"市场概况：{ai_summary}\n\n"

        if top_cities:
            ctx += "**TOP 城市（按职位数）：**\n"
            for c in top_cities:
                ctx += f"- {c['city']}：{c['count']} 个职位，均薪 {c['avg_salary']}K/月\n"
            ctx += "\n"

        if top_jobs:
            ctx += "**热门岗位：**\n"
            for j in top_jobs:
                ctx += f"- {j['title']}（{j['count']} 个）\n"
            ctx += "\n"

        if salary_info:
            ctx += f"薪资概况：均薪 {salary_info.get('avg_salary', 'N/A')}K/月，"
            ctx += f"中位数 {salary_info.get('median_salary', 'N/A')}K/月，"
            ctx += f"高薪占比（30K+）{salary_info.get('high_salary_pct', 'N/A')}%\n\n"

        if health:
            ctx += f"市场健康度：{health.get('score', 'N/A')} 分（{health.get('label', 'N/A')}）\n"
            factors = health.get('factors', [])
            if factors:
                ctx += f"评估因素：{'、'.join(factors)}\n"

        return ctx
    except Exception as e:
        return f"（数据上下文加载失败：{e}）\n"


@router.post("/chat", response_model=BaseResponse)
async def ai_chat(request: AIChatRequest) -> BaseResponse:
    """
    AI 大模型对话接口

    支持 DeepSeek、硅基流动、OpenAI、Gemini 等平台。
    自动注入平台招聘数据作为对话上下文，让 AI 能够基于真实数据回答。

    使用方式：
    1. 在任意 AI 平台注册获取 API Key
    2. 传入对话历史和 API Key 即可开始对话

    推荐平台：
    - 硅基流动 (siliconflow) — 聚合 DeepSeek/Qwen，中文优秀，注册送额度
    - DeepSeek — 中文最强，有免费额度
    """
    from analysis.ai_report_enhancer import chat_with_ai

    # 转换消息格式
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # 如果需要，注入市场数据上下文
    if request.include_context:
        context = _build_context_prompt()
        if context:
            # 在 system prompt 和第一条 user 消息之间插入上下文
            system_msg = next(
                (m for m in messages if m["role"] == "system"), None
            )
            if system_msg:
                system_msg["content"] = system_msg["content"] + "\n\n" + context
            else:
                # 没有 system 消息时，插入一条
                messages.insert(0, {
                    "role": "system",
                    "content": _CHAT_SYSTEM_PROMPT + "\n\n" + context,
                })

    # 确保至少有一个 system prompt
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": _CHAT_SYSTEM_PROMPT})

    # 调用 AI
    reply = chat_with_ai(
        messages=messages,
        provider=request.provider,
        api_key=request.api_key,
        model=request.model or "",
        base_url=request.base_url or "",
    )

    if reply is None:
        return BaseResponse(
            code=500,
            message="AI 调用失败，请检查 API Key 和网络连接",
            data=None,
        )

    return BaseResponse(
        code=200,
        message="ok",
        data={
            "reply": reply,
            "provider": request.provider,
            "model": request.model or "默认模型",
        },
    )
