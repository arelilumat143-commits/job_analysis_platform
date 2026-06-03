# CORS中间件配置
"""
跨域资源共享(CORS)配置
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app: FastAPI) -> None:
    """
    配置CORS中间件
    
    允许前端跨域访问API
    
    Args:
        app: FastAPI应用实例
    """
    app.add_middleware(
        CORSMiddleware,
        # 允许的源列表（生产环境应限制为具体域名）
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8501",  # Streamlit默认端口
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8501",
            "http://127.0.0.1:8000",
            "*"  # 开发环境允许所有源，生产环境应限制
        ],
        # 允许的请求方法
        allow_methods=["*"],
        # 允许的请求头
        allow_headers=["*"],
        # 是否允许携带凭证
        allow_credentials=True
    )
