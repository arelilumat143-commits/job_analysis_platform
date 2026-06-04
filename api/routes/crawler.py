# 爬虫任务管理接口
"""
提供爬虫管理相关的API接口：
- POST /api/crawler/start - 启动爬虫任务
- GET /api/crawler/status - 查询爬虫状态
- GET /api/crawler/sources - 查看可用数据源
"""

import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks

from api.models import BaseResponse, CrawlerStartRequest, CrawlerStartResponse, CrawlerStatusResponse
from api.services.crawler_service import CrawlerService

router = APIRouter(prefix="/crawler", tags=["爬虫管理"])
crawler_service = CrawlerService()

# 爬虫任务状态存储（内存中，生产环境应使用Redis）
crawler_tasks: Dict[str, Dict[str, Any]] = {}


def run_crawler_task(task_id: str, source: str, city: Optional[str], keyword: Optional[str], max_pages: int):
    """后台运行爬虫任务"""
    try:
        crawler_tasks[task_id]["status"] = "running"
        crawler_tasks[task_id]["message"] = "爬虫运行中..."

        # 执行爬虫
        result = crawler_service.run_crawler(source=source, city=city, keyword=keyword, max_pages=max_pages)

        # 根据 success 字段判断实际结果
        if result.get("success"):
            crawler_tasks[task_id]["status"] = "completed"
            crawler_tasks[task_id]["message"] = f"爬取完成，新增 {result.get('added_count', 0)} 条数据"
        else:
            crawler_tasks[task_id]["status"] = "failed"
            crawler_tasks[task_id]["message"] = result.get("message", "未知错误")
        crawler_tasks[task_id]["result"] = result

    except Exception as e:
        crawler_tasks[task_id]["status"] = "failed"
        crawler_tasks[task_id]["message"] = f"爬虫执行异常: {type(e).__name__}: {str(e)}"


@router.post("/start", response_model=BaseResponse)
async def start_crawler(
    request: CrawlerStartRequest,
    background_tasks: BackgroundTasks
) -> BaseResponse:
    """
    启动爬虫任务
    
    - source: 数据源(boss/zhilian/qiancheng/shixiseng)
    - city: 城市（可选）
    - keyword: 关键词（可选）
    """
    # 生成任务ID
    task_id = str(uuid.uuid4())[:8]
    
    # 记录任务状态
    crawler_tasks[task_id] = {
        "task_id": task_id,
        "source": request.source,
        "city": request.city,
        "keyword": request.keyword,
        "max_pages": request.max_pages,
        "status": "pending",
        "message": "任务已创建，等待执行",
        "total_collected": 0,
        "result": None
    }
    
    # 后台执行爬虫
    background_tasks.add_task(run_crawler_task, task_id, request.source, request.city, request.keyword, request.max_pages)
    
    return BaseResponse(
        code=200,
        message="任务已启动",
        data={
            "task_id": task_id,
            "status": "pending",
            "message": "爬虫任务已在后台启动"
        }
    )


@router.get("/status", response_model=BaseResponse)
async def get_crawler_status() -> BaseResponse:
    """
    查询爬虫状态
    
    返回所有爬虫任务的状态
    """
    # 更新总采集数量
    total = crawler_service.get_total_jobs()
    
    running_tasks = [
        {
            "task_id": task_id,
            "source": task["source"],
            "status": task["status"],
            "message": task["message"]
        }
        for task_id, task in crawler_tasks.items()
        if task["status"] in ["pending", "running"]
    ]
    
    return BaseResponse(
        code=200,
        message="ok",
        data={
            "status": "running" if running_tasks else "idle",
            "total_collected": total,
            "running_tasks": running_tasks
        }
    )


@router.get("/sources", response_model=BaseResponse)
async def get_data_sources() -> BaseResponse:
    """
    查看可用数据源
    
    返回支持的所有招聘网站数据源
    """
    sources = crawler_service.get_available_sources()
    
    return BaseResponse(
        code=200,
        message="ok",
        data=sources
    )


@router.get("/tasks", response_model=BaseResponse)
async def get_crawler_tasks(
    status: Optional[str] = None
) -> BaseResponse:
    """
    获取爬虫任务列表
    
    - status: 任务状态过滤（pending/running/completed/failed）
    """
    tasks = list(crawler_tasks.values())
    
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    # 按创建时间倒序
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return BaseResponse(
        code=200,
        message="ok",
        data=tasks
    )


@router.get("/task/{task_id}", response_model=BaseResponse)
async def get_task_detail(task_id: str) -> BaseResponse:
    """
    获取任务详情
    """
    if task_id not in crawler_tasks:
        return BaseResponse(
            code=404,
            message="任务不存在",
            data=None
        )
    
    return BaseResponse(
        code=200,
        message="ok",
        data=crawler_tasks[task_id]
    )


# ========== 详情页抓取 ==========

detail_scrape_status = {
    "running": False,
    "stats": {"total": 0, "success": 0, "updated": 0, "failed": 0, "skipped": 0},
    "city": None,
    "limit": None,
}


def run_detail_scrape_background(city: str = None, limit: int = 100, concurrency: int = 3):
    """后台运行详情页爬虫"""
    import asyncio
    from crawlers.detail_scraper import DetailScraper

    async def _run():
        detail_scrape_status["running"] = True
        detail_scrape_status["stats"] = {"total": 0, "success": 0, "updated": 0, "failed": 0, "skipped": 0}
        scraper = DetailScraper(concurrency=concurrency, delay_range=(1.0, 3.0))
        # 设置进度回调
        def on_progress(stats):
            detail_scrape_status["stats"] = stats
        scraper.progress_callback = on_progress
        try:
            result = await scraper.run(city=city, limit=limit, resume=True)
            detail_scrape_status["stats"] = result
        finally:
            detail_scrape_status["running"] = False

    asyncio.run(_run())


@router.post("/detail-scrape", response_model=BaseResponse)
async def start_detail_scrape(
    city: str = None,
    limit: int = 100,
    concurrency: int = 3,
    background_tasks: BackgroundTasks = None,
) -> BaseResponse:
    """
    启动详情页爬虫

    - city: 按城市筛选（可选）
    - limit: 限制数量（默认100，设为0表示不限制）
    - concurrency: 并发数（默认3）
    """
    if detail_scrape_status["running"]:
        return BaseResponse(
            code=400,
            message="详情页爬虫已在运行中",
            data=detail_scrape_status["stats"],
        )

    detail_scrape_status["city"] = city
    detail_scrape_status["limit"] = limit if limit > 0 else None

    background_tasks.add_task(
        run_detail_scrape_background,
        city=city,
        limit=limit if limit > 0 else 100,
        concurrency=concurrency,
    )

    return BaseResponse(
        code=200,
        message=f"详情页爬虫已启动（城市:{city or '全部'}, 限制:{limit}条）",
        data={"status": "started"},
    )


@router.get("/detail-scrape/status", response_model=BaseResponse)
async def get_detail_scrape_status() -> BaseResponse:
    """查询详情页爬虫状态"""
    return BaseResponse(
        code=200,
        message="ok",
        data={
            "running": detail_scrape_status["running"],
            "city": detail_scrape_status["city"],
            "limit": detail_scrape_status["limit"],
            "stats": detail_scrape_status["stats"],
        },
    )


@router.post("/detail-scrape/stop", response_model=BaseResponse)
async def stop_detail_scrape() -> BaseResponse:
    """停止详情页爬虫"""
    if not detail_scrape_status["running"]:
        return BaseResponse(code=400, message="没有正在运行的详情页爬虫", data=None)
    # 通过设置标志位来停止（scraper 内部检查）
    detail_scrape_status["running"] = False
    return BaseResponse(code=200, message="详情页爬虫停止信号已发送", data=None)
