# FastAPI应用入口
"""
城市招聘市场智能分析平台 - FastAPI后端

提供RESTful API接口：
- /api/jobs - 职位CRUD
- /api/analysis - 数据分析
- /api/ai - AI智能分析
- /api/crawler - 爬虫管理
"""

import sys
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 导入路由
from api.routes import (
    jobs_router, analysis_router, ai_router, crawler_router,
    prediction_router, matching_router,
)

# 创建FastAPI应用
app = FastAPI(
    title="城市招聘市场智能分析平台 API",
    description="""
## 城市招聘市场智能分析平台

提供完整的招聘数据分析API服务，包括：

### 功能模块
- **职位管理** (`/api/jobs`) - 职位列表查询、详情查看、全文搜索、统计概览
- **数据分析** (`/api/analysis`) - 薪资分析、城市分析、技能分析、行业分析
- **AI分析** (`/api/ai`) - 薪资预测、岗位聚类、技能趋势
- **爬虫管理** (`/api/crawler`) - 启动爬虫、查看状态、管理数据源

### 技术栈
- FastAPI - 高性能Web框架
- Pydantic - 数据验证
- SQLAlchemy - ORM数据库访问
- Uvicorn - ASGI服务器
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# 异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": f"服务器内部错误: {str(exc)}",
            "data": None
        }
    )


# 挂载路由
app.include_router(jobs_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(crawler_router, prefix="/api")
app.include_router(prediction_router, prefix="/api")
app.include_router(matching_router, prefix="/api")


# 健康检查接口
@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查接口
    
    用于监控服务状态
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "job-analysis-platform-api",
        "version": "1.0.0"
    }


# 根路径
@app.get("/", tags=["系统"])
async def root():
    """
    根路径
    
    返回API基本信息
    """
    return {
        "name": "城市招聘市场智能分析平台 API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# API信息
@app.get("/api/info", tags=["系统"])
async def api_info():
    """
    API信息
    
    返回API的详细信息
    """
    return {
        "code": 200,
        "message": "ok",
        "data": {
            "name": "城市招聘市场智能分析平台 API",
            "version": "1.0.0",
            "description": "提供招聘数据分析的RESTful API",
            "endpoints": {
                "jobs": "/api/jobs",
                "analysis": "/api/analysis",
                "ai": "/api/ai",
                "crawler": "/api/crawler"
            },
            "documentation": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 50)
    print("城市招聘市场智能分析平台 - FastAPI后端")
    print("=" * 50)
    print("启动服务...")
    print("API文档: http://localhost:8000/docs")
    print("=" * 50)
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
