"""
招聘数据分析平台 — Streamlit 主入口（莫兰迪极简风 UI）。

多页面应用，集成数据清洗、技能 NLP、薪资预测与岗位推荐等分析能力。
运行方式（在项目根目录）::

    streamlit run web/app.py

设计风格：
  - 当代极简现代风 + 超大留白 + 低饱和莫兰迪配色
  - 主色柔蓝 #5B8DEF，全局极浅灰背景 #FAFAFA
  - 白色卡片 + 极浅阴影，无边框设计
  - 大圆角 16px，超轻量微动效
  - Plotly 低饱和柔和配色，图表简洁干净
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

# 将项目根目录加入模块搜索路径，确保可导入 config / storage / analysis
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis.data_cleaner import data_cleaner
from analysis.job_recommender import job_recommender
from analysis.salary_predictor_v2 import SalaryPredictorV2, salary_predictor_v2 as salary_predictor
from analysis.skill_nlp import skill_analyzer
from analysis.ai_report_enhancer import (
    is_ai_available, get_provider_name,
    generate_ai_report, collect_report_stats,
    collect_skill_stats, collect_model_stats,
)
from config.settings import BASE_DIR, settings
from storage.database import db_manager

# ============================================================================
# 莫兰迪设计系统 — 色彩 & 常量
# ============================================================================

# ── 品牌色（低饱和度柔蓝系） ──
_PRIMARY      = "#5B8DEF"   # 主色 — 柔蓝
_PRIMARY_LIGHT = "#8BABF0"  # 浅柔蓝
_PRIMARY_SOFT  = "#EEF2FB"  # 极浅蓝底
_PRIMARY_SUBTLE = "#F6F8FD" # 更淡的蓝底

# ── 辅助色（低饱和莫兰迪绿/红/橙，仅状态提示） ──
_ACCENT_GREEN  = "#7EB8A0"  # 柔绿
_ACCENT_GREEN_SOFT = "#EEF5F1"
_ACCENT_RED    = "#C48B8B"  # 柔红
_ACCENT_RED_SOFT = "#FBF3F3"
_ACCENT_ORANGE = "#C9A87C"  # 柔橙
_ACCENT_PURPLE = "#9B8EC4"  # 柔紫

# ── 背景与卡片 ──
_BG_PAGE   = "#FAFAFA"   # 全局极浅灰底
_BG_CARD   = "#FFFFFF"   # 纯白卡片
_BG_SIDEBAR = "#F5F6F8"  # 侧边栏浅灰底

# ── 文字层级 ──
_TEXT_1 = "#2C2C2C"   # 主文字 — 深灰黑
_TEXT_2 = "#6B6B6B"   # 次文字 — 柔灰
_TEXT_3 = "#A0A0A0"   # 辅助文字 — 浅灰

# ── 边框与阴影（极简克制） ──
_BORDER_LIGHT = "#F0F0F0"  # 微边框（仅必要时使用）
_SHADOW_CARD  = "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)"
_SHADOW_HOVER = "0 2px 8px rgba(0,0,0,0.06)"
_RADIUS = "16px"
_RADIUS_SM = "10px"

# ── 莫兰迪图表配色（低饱和系列） ──
_CHART_COLORS = [
    "#5B8DEF", "#7EB8A0", "#9B8EC4", "#C9A87C",
    "#8BABF0", "#A8D0C0", "#B8AED8", "#D4BC9A",
    "#6C9ADF", "#8FC0AB", "#A398C8", "#CFB488",
]
_CHART_BLUES  = ["#EEF2FB", "#D4E0F8", "#A8C2F2", "#7BA6EC", "#5B8DEF"]
_CHART_GREENS = ["#EDF5F1", "#D4EBE2", "#A8D8C4", "#7EC5A6", "#5EB28E"]

# ── 导航页面列表 ──
_NAV_ITEMS: list[dict[str, str]] = [
    {"label": "首页概览",  "icon": "◉"},
    {"label": "薪资分析",  "icon": "◇"},
    {"label": "技能分析",  "icon": "○"},
    {"label": "岗位推荐",  "icon": "□"},
    {"label": "数据管理",  "icon": "△"},
    {"label": "AI智能报告", "icon": "▽"},
]
_NAV_PAGES: list[str] = [item["label"] for item in _NAV_ITEMS]


# ============================================================================
# 全局 CSS 注入
# ============================================================================

def _inject_global_css() -> None:
    """注入莫兰迪极简风格全局 CSS。"""
    st.markdown(f"""
    <style>
    /* ================================================================
       莫兰迪极简风格 — 全局 CSS
       核心原则：超大留白、无边框、柔阴影、大圆角、低饱和、微动效
       ================================================================ */

    /* ----- 根变量 ----- */
    :root {{
        --primary: {_PRIMARY};
        --primary-light: {_PRIMARY_LIGHT};
        --primary-soft: {_PRIMARY_SOFT};
        --bg: {_BG_PAGE};
        --card: {_BG_CARD};
        --text-1: {_TEXT_1};
        --text-2: {_TEXT_2};
        --text-3: {_TEXT_3};
        --shadow: {_SHADOW_CARD};
        --radius: {_RADIUS};
        --radius-sm: {_RADIUS_SM};
    }}

    /* ----- 全局背景 & 主容器 ----- */
    .stApp {{
        background: {_BG_PAGE};
    }}

    .block-container {{
        padding: 2rem 3rem 3rem 3rem;
        max-width: 1440px;
    }}

    /* ----- 侧边栏 — 浅色极简 ----- */
    [data-testid="stSidebar"] {{
        background: {_BG_SIDEBAR};
        border-right: 1px solid {_BORDER_LIGHT};
    }}
    [data-testid="stSidebar"] * {{
        color: {_TEXT_1} !important;
        font-weight: 400 !important;
    }}
    [data-testid="stSidebar"] .stRadio > div {{
        gap: 2px;
    }}
    [data-testid="stSidebar"] .stRadio label {{
        font-size: 14px !important;
        padding: 8px 16px !important;
        border-radius: 12px !important;
        margin: 0 !important;
        transition: background 0.3s ease !important;
        color: {_TEXT_2} !important;
    }}
    [data-testid="stSidebar"] .stRadio label:hover {{
        background: rgba(91,141,239,0.06) !important;
    }}
    [data-testid="stSidebar"] .stRadio label:has(input:checked) {{
        background: {_PRIMARY_SOFT} !important;
        color: {_PRIMARY} !important;
        font-weight: 500 !important;
    }}
    [data-testid="stSidebar"] .stRadio label:has(input:checked) * {{
        color: {_PRIMARY} !important;
        font-weight: 500 !important;
    }}

    /* ----- 按钮 — 极简填充/线框 ----- */
    .stButton > button {{
        border-radius: 12px !important;
        font-weight: 500 !important;
        padding: 8px 22px !important;
        transition: all 0.3s ease !important;
        letter-spacing: 0.01em;
        font-size: 14px !important;
        border: none !important;
    }}
    .stButton > button:hover {{
        filter: brightness(0.96);
        transform: none;
        box-shadow: none !important;
    }}
    .stButton > button[kind="primary"] {{
        background: {_PRIMARY} !important;
        color: #FFF !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        background: {_PRIMARY_LIGHT} !important;
    }}
    .stDownloadButton > button {{
        border-radius: 12px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }}

    /* ----- Tab — 极简下划线 ----- */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background: transparent;
        border-bottom: 1px solid {_BORDER_LIGHT};
        padding-bottom: 0;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 0 !important;
        padding: 12px 24px !important;
        font-weight: 400 !important;
        color: {_TEXT_3} !important;
        background: transparent !important;
        border: none !important;
        transition: all 0.3s ease;
        font-size: 14px !important;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: {_TEXT_2} !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: {_PRIMARY} !important;
        border-bottom: 2px solid {_PRIMARY} !important;
        font-weight: 500 !important;
        background: transparent !important;
    }}

    /* ----- 表单 — 无边框极简 ----- */
    [data-testid="stForm"] {{
        background: {_BG_CARD};
        border: none;
        border-radius: {_RADIUS};
        padding: 32px 36px;
        box-shadow: {_SHADOW_CARD};
    }}
    .stTextInput input, .stSelectbox [data-baseweb="select"] {{
        border-radius: 10px !important;
        border: 1px solid {_BORDER_LIGHT} !important;
        transition: border-color 0.3s ease !important;
        padding: 10px 14px !important;
    }}
    .stTextInput input:focus, .stSelectbox [data-baseweb="select"]:focus {{
        border-color: {_PRIMARY} !important;
        box-shadow: 0 0 0 2px {_PRIMARY_SOFT} !important;
    }}

    /* ----- 数据表格 — 极简无线框 ----- */
    [data-testid="stDataFrame"] {{
        border: none;
        border-radius: 12px;
        overflow: hidden;
    }}
    [data-testid="stDataFrame"] table {{
        border-collapse: collapse;
    }}
    [data-testid="stDataFrame"] th {{
        background: {_BG_SIDEBAR} !important;
        color: {_TEXT_2} !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        padding: 12px 16px !important;
        border-bottom: 1px solid {_BORDER_LIGHT} !important;
    }}
    [data-testid="stDataFrame"] td {{
        padding: 10px 16px !important;
        border: none !important;
        font-size: 13px !important;
        color: {_TEXT_1} !important;
    }}

    /* ----- Alert 消息 — 柔化 ----- */
    [data-testid="stAlert"] {{
        border-radius: 12px;
        border: none;
        border-left: 3px solid {_PRIMARY};
        background: {_PRIMARY_SUBTLE};
        padding: 16px 20px;
    }}

    /* ----- 指标卡片容器 ----- */
    .metric-card {{
        background: {_BG_CARD};
        border-radius: {_RADIUS};
        padding: 28px 24px;
        box-shadow: {_SHADOW_CARD};
        text-align: center;
        transition: box-shadow 0.4s ease;
    }}
    .metric-card:hover {{
        box-shadow: {_SHADOW_HOVER};
    }}
    .metric-card .metric-icon {{
        font-size: 1.5rem;
        margin-bottom: 10px;
        opacity: 0.7;
    }}
    .metric-card .metric-value {{
        font-size: 2.2rem;
        font-weight: 600;
        color: {_TEXT_1};
        line-height: 1.2;
        letter-spacing: -0.02em;
    }}
    .metric-card .metric-label {{
        font-size: 0.82rem;
        color: {_TEXT_3};
        margin-top: 6px;
        font-weight: 400;
    }}

    /* ----- 内容卡片 ----- */
    .content-card {{
        background: {_BG_CARD};
        border-radius: {_RADIUS};
        padding: 28px 32px;
        box-shadow: {_SHADOW_CARD};
        margin-bottom: 28px;
    }}

    /* ----- 页面标题区 ----- */
    .page-hero {{
        margin-bottom: 36px;
        padding-bottom: 24px;
        border-bottom: 1px solid {_BORDER_LIGHT};
    }}
    .page-hero .page-title {{
        font-size: 1.5rem;
        font-weight: 600;
        color: {_TEXT_1};
        margin-bottom: 6px;
        letter-spacing: -0.01em;
    }}
    .page-hero .page-subtitle {{
        font-size: 0.88rem;
        color: {_TEXT_3};
        font-weight: 400;
    }}

    /* ----- 提示引导卡片 ----- */
    .guide-card {{
        background: {_PRIMARY_SUBTLE};
        border: none;
        border-radius: {_RADIUS};
        padding: 20px 24px;
        margin-bottom: 24px;
    }}
    .guide-card p {{
        margin: 0;
        color: {_TEXT_2};
        font-size: 0.88rem;
    }}

    /* ----- 报告渲染区 ----- */
    .report-box {{
        background: {_BG_CARD};
        border-radius: {_RADIUS};
        padding: 32px 36px;
        box-shadow: {_SHADOW_CARD};
        line-height: 1.8;
    }}

    /* ----- 隐藏默认元素 ----- */
    #MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent !important; }}

    /* ----- 滚动条极简 ----- */
    ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
    ::-webkit-scrollbar-thumb {{
        background: #E0E0E0;
        border-radius: 2px;
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: #C8C8C8; }}
    </style>
    """, unsafe_allow_html=True)


# ============================================================================
# 图表统一风格（莫兰迪低饱和）
# ============================================================================

def _chart_layout(
    title: str = "",
    height: int = 380,
    show_legend: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """返回莫兰迪风格的 Plotly 统一布局配置。"""
    return dict(
        title=dict(
            text=title,
            font=dict(size=14, color=_TEXT_1, family="PingFang SC, Microsoft YaHei, sans-serif"),
            x=0.02,
        ),
        height=height,
        showlegend=show_legend,
        margin=dict(l=16, r=16, t=48, b=16),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            gridcolor="#F5F5F5",
            zeroline=False,
            linecolor=_BORDER_LIGHT,
            title_font=dict(size=12, color=_TEXT_2),
            tickfont=dict(size=11, color=_TEXT_2),
        ),
        yaxis=dict(
            gridcolor="#F5F5F5",
            zeroline=False,
            linecolor=_BORDER_LIGHT,
            title_font=dict(size=12, color=_TEXT_2),
            tickfont=dict(size=11, color=_TEXT_2),
        ),
        font=dict(family="PingFang SC, Microsoft YaHei, sans-serif", color=_TEXT_2),
        colorway=_CHART_COLORS,
        **kwargs,
    )


def _apply_chart_style(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    """对已创建的图表统一应用莫兰迪极简样式。"""
    fig.update_layout(**_chart_layout(title=title, height=height))
    fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    return fig


# ============================================================================
# 指标卡片组件
# ============================================================================

def _metric_card(icon: str, value: str, label: str) -> None:
    """渲染一个莫兰迪风格的指标卡片。"""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">{icon}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# 数据加载（缓存 — 原封不动）
# ============================================================================

_jobs_cache: list[dict[str, Any]] | None = None

def load_jobs(use_cache: bool = True) -> list[dict[str, Any]]:
    """从数据库加载全部职位。"""
    global _jobs_cache
    if use_cache and _jobs_cache is not None:
        return _jobs_cache
    _jobs_cache = db_manager.get_all_jobs()
    return _jobs_cache


def clear_jobs_cache() -> None:
    """清除职位数据缓存。"""
    global _jobs_cache
    _jobs_cache = None


def filter_jobs(
    jobs: list[dict[str, Any]],
    keyword: str = "",
    city: str = "全部",
    experience: str = "全部",
    salary_min: float | None = None,
    salary_max: float | None = None,
) -> list[dict[str, Any]]:
    """多条件筛选职位列表，支持关键词搜索标题/公司/技能。"""
    result = jobs

    # 关键词搜索（标题、公司、技能）
    if keyword.strip():
        kw = keyword.strip().lower()
        result = [
            j for j in result
            if kw in str(j.get("title", "")).lower()
            or kw in str(j.get("company", "")).lower()
            or kw in str(j.get("skills", "")).lower()
            or kw in str(j.get("description", "")).lower()
        ]

    # 城市筛选
    if city and city != "全部":
        result = [
            j for j in result
            if str(j.get("city", "")).replace("市", "") == city.replace("市", "")
        ]

    # 经验筛选
    if experience and experience != "全部":
        result = [j for j in result if j.get("experience") == experience]

    # 薪资范围筛选
    if salary_min is not None:
        result = [
            j for j in result
            if j.get("salary_min") and float(j["salary_min"]) >= salary_min
        ]
    if salary_max is not None:
        result = [
            j for j in result
            if j.get("salary_max") and float(j["salary_max"]) <= salary_max
        ]

    return result


def _salary_mid(job: dict[str, Any]) -> float | None:
    """计算职位薪资中位数（K/月）。"""
    try:
        smin = float(job["salary_min"]) if job.get("salary_min") is not None else None
        smax = float(job["salary_max"]) if job.get("salary_max") is not None else None
    except (TypeError, ValueError):
        return None
    if smin is None or smax is None or smin <= 0 or smax <= 0:
        return None
    if smin > smax:
        smin, smax = smax, smin
    return (smin + smax) / 2.0


def compute_overview_metrics(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    计算首页关键指标。

    Returns:
        total_jobs, avg_salary, top_city, top_skill
    """
    if not jobs:
        return {
            "total_jobs": 0,
            "avg_salary": 0.0,
            "top_city": "—",
            "top_skill": "—",
        }

    salaries = [_salary_mid(j) for j in jobs]
    valid_salaries = [s for s in salaries if s is not None]
    avg_salary = sum(valid_salaries) / len(valid_salaries) if valid_salaries else 0.0

    city_counter: Counter[str] = Counter()
    for job in jobs:
        city = job.get("city") or "未知"
        city_counter[str(city).replace("市", "")] += 1
    top_city = city_counter.most_common(1)[0][0] if city_counter else "—"

    try:
        skill_freq = skill_analyzer.get_skills_frequency(top_n=1)
        top_skill = skill_freq.most_common(1)[0][0] if skill_freq else "—"
    except Exception:
        top_skill = "—"

    return {
        "total_jobs": len(jobs),
        "avg_salary": round(avg_salary, 1),
        "top_city": top_city,
        "top_skill": top_skill,
    }


# ============================================================================
# 侧边栏（莫兰迪极简版）
# ============================================================================

def render_sidebar() -> str:
    """
    渲染左侧导航栏（莫兰迪极简版）。

    Returns:
        当前选中的页面名称。
    """
    # ── 品牌标识区 ──
    st.sidebar.markdown(f"""
    <div style="padding: 24px 16px 20px 16px; margin-bottom: 8px;">
        <div style="font-size: 17px; font-weight: 600; color: {_TEXT_1}; letter-spacing: 0.02em;">
            招聘分析平台
        </div>
        <div style="font-size: 12px; color: {_TEXT_3}; margin-top: 4px; font-weight: 400;">
            Job Analytics
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 数据库状态 ──
    db_label = settings.database.backend.upper()
    db_dot = _ACCENT_GREEN if settings.database.backend == "mysql" else _ACCENT_ORANGE
    st.sidebar.markdown(f"""
    <div style="display:flex; align-items:center; gap:8px; padding:8px 18px; margin:0 12px 20px 12px;
                background: #FFF; border-radius: 12px; box-shadow:{_SHADOW_CARD}; font-size: 12px;">
        <span style="width:7px; height:7px; border-radius:50%; background:{db_dot}; display:inline-block;"></span>
        <span style="color:{_TEXT_3};">数据库</span>
        <span style="color:{_TEXT_1}; font-weight:500; margin-left:auto;">{db_label}</span>
    </div>
    """, unsafe_allow_html=True)

    # ── 导航标题 ──
    st.sidebar.markdown(
        f'<p style="font-size:11px; color:{_TEXT_3}; padding:0 18px; margin:0 0 4px 0;'
        f'text-transform:uppercase; letter-spacing:0.12em; font-weight:500;">导航</p>',
        unsafe_allow_html=True,
    )

    # ── 导航菜单 ──
    nav_options = [f"{item['icon']}  {item['label']}" for item in _NAV_ITEMS]
    selected_display = st.sidebar.radio(
        "导航",
        nav_options,
        label_visibility="collapsed",
    )

    for item in _NAV_ITEMS:
        if selected_display.startswith(item["icon"]):
            selected_page = item["label"]
            break
    else:
        selected_page = _NAV_PAGES[0]

    # ── 分隔（留白） ──
    st.sidebar.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    # ── 系统信息 ──
    st.sidebar.markdown(
        f'<p style="font-size:11px; color:{_TEXT_3}; padding:0 18px; margin:0 0 8px 0;'
        f'text-transform:uppercase; letter-spacing:0.12em; font-weight:500;">系统</p>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(f"""
    <div style="font-size:12px; color:{_TEXT_3}; padding:0 18px; line-height:2.2;">
        <div style="display:flex;justify-content:space-between;">
            <span>项目</span><span style="color:{_TEXT_2};">analysis_platform</span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>数据库</span><span style="color:{_TEXT_2};">job_analysis</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 刷新按钮 ──
    st.sidebar.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div style="padding:0 12px;">', unsafe_allow_html=True)
    if st.sidebar.button("刷新数据缓存", width='stretch'):
        clear_jobs_cache()
        job_recommender.refresh_index()
        st.sidebar.success("已刷新")
        st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    # ── 底部 ──
    st.sidebar.markdown(f"""
    <div style="position:fixed; bottom:24px; left:24px; font-size:10px; color:{_TEXT_3};">
        v2.0 · Morandi Edition
    </div>
    """, unsafe_allow_html=True)

    return selected_page


# ============================================================================
# 页面：首页概览
# ============================================================================

def page_overview(jobs: list[dict[str, Any]]) -> None:
    """首页概览：关键指标卡片与基础图表。"""
    # ── 页面标题 ──
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">首页概览</div>
        <div class="page-subtitle">平台数据总览与核心指标一览，实时掌握招聘市场动态</div>
    </div>
    """, unsafe_allow_html=True)

    metrics = compute_overview_metrics(jobs)

    # ── 四列指标卡片 ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card("◉", str(metrics["total_jobs"]), "总职位数")
    with c2:
        _metric_card("◇", f"{metrics['avg_salary']} K", "平均月薪")
    with c3:
        _metric_card("○", metrics["top_city"], "热门城市")
    with c4:
        _metric_card("□", metrics["top_skill"], "热门技能")

    if not jobs:
        st.markdown("""
        <div class="guide-card">
            <p>暂无职位数据，请前往「数据管理」页面导入示例数据或启动爬虫采集真实数据。</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── 留白分隔 ──
    st.markdown('<div style="height:28px;"></div>', unsafe_allow_html=True)

    # ── 图表行 1：城市 + 薪资 ──
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        city_counts = Counter(
            str(j.get("city") or "未知").replace("市", "") for j in jobs
        )
        df_city = pd.DataFrame(city_counts.most_common(10), columns=["城市", "职位数"])
        fig_city = px.bar(
            df_city, x="城市", y="职位数",
            color="职位数",
            color_continuous_scale=[_CHART_BLUES[1], _CHART_BLUES[2], _CHART_BLUES[4]],
        )
        fig_city = _apply_chart_style(fig_city, title="城市职位分布 Top 10", height=380)
        fig_city.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_city, width='stretch', config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        salary_data = [
            {"薪资中位数 (K/月)": mid}
            for j in jobs
            if (mid := _salary_mid(j)) is not None
        ]
        if salary_data:
            df_salary = pd.DataFrame(salary_data)
            fig_sal = px.histogram(
                df_salary, x="薪资中位数 (K/月)", nbins=25,
                color_discrete_sequence=[_PRIMARY],
            )
            fig_sal = _apply_chart_style(fig_sal, title="薪资分布直方图", height=380)
            fig_sal.update_traces(marker_line_width=0, opacity=0.85)
            st.plotly_chart(fig_sal, width='stretch', config={"displayModeBar": False})
        else:
            st.info("暂无有效薪资数据。")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 留白 ──
    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

    # ── 图表行 2：来源 + 行业 ──
    c3, c4 = st.columns(2)

    with c3:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        source_counts = Counter(j.get("source") or "未知" for j in jobs)
        df_source = pd.DataFrame(list(source_counts.items()), columns=["来源", "数量"])
        fig_pie = px.pie(
            df_source, names="来源", values="数量",
            color_discrete_sequence=_CHART_COLORS[:5],
        )
        fig_pie = _apply_chart_style(fig_pie, title="招聘来源占比", height=340)
        fig_pie.update_traces(textposition="inside", textinfo="percent+label", hole=0.45)
        st.plotly_chart(fig_pie, width='stretch', config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        industry_counts = Counter(
            (j.get("industry") or "未知").strip()
            for j in jobs if (j.get("industry") or "").strip()
        )
        if industry_counts:
            df_ind = pd.DataFrame(industry_counts.most_common(8), columns=["行业", "数量"])
            fig_ind = px.bar(
                df_ind, x="数量", y="行业", orientation="h",
                color="数量",
                color_continuous_scale=[_CHART_GREENS[1], _CHART_GREENS[2], _CHART_GREENS[4]],
            )
            fig_ind = _apply_chart_style(fig_ind, title="行业分布 Top 8", height=340)
            fig_ind.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig_ind, width='stretch', config={"displayModeBar": False})
        else:
            st.info("暂无行业数据。")
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# 页面：薪资分析
# ============================================================================

def page_salary(jobs: list[dict[str, Any]]) -> None:
    """薪资分析：分布可视化、模型训练与单条预测。"""
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">薪资分析</div>
        <div class="page-subtitle">基于XGBoost + TF-IDF标题特征的薪资预测，含特征重要性分析与在线预测</div>
    </div>
    """, unsafe_allow_html=True)

    if len(jobs) < 10:
        st.markdown("""
        <div class="guide-card">
            <p>有效职位不足 10 条，请先在「数据管理」补充数据后再训练模型。</p>
        </div>
        """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["薪资分布", "模型训练", "薪资预测"])

    # ── Tab1: 薪资分布 ──
    with tab1:
        records = []
        for job in jobs:
            mid = _salary_mid(job)
            if mid is None:
                continue
            records.append({
                "城市": str(job.get("city") or "未知"),
                "行业": str(job.get("industry") or "未知"),
                "薪资中位数 (K/月)": mid,
            })
        if records:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            df = pd.DataFrame(records)
            top_cities = df["城市"].value_counts().head(8).index.tolist()
            df_plot = df[df["城市"].isin(top_cities)]
            fig = px.box(
                df_plot, x="城市", y="薪资中位数 (K/月)", color="城市",
                color_discrete_sequence=_CHART_COLORS,
            )
            fig = _apply_chart_style(fig, title="各城市薪资箱线图 (K/月)", height=440)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("暂无薪资数据。")

    # ── Tab2: 模型训练 ──
    with tab2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("##### XGBoost 增强回归模型（含标题TF-IDF + 技能分类）")

        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            train_clicked = st.button("开始训练", type="primary", width='stretch')
        with col_info:
            if salary_predictor.is_trained and salary_predictor.metrics:
                m = salary_predictor.metrics
                st.markdown(
                    f'<span style="color:{_ACCENT_GREEN};font-weight:500;">模型已就绪</span>'
                    f'&nbsp;&nbsp;<span style="color:{_TEXT_3};">'
                    f'R²={m.get("r2",0):.4f}  MAE={m.get("mae",0):.2f}K  RMSE={m.get("rmse",0):.2f}K</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<span style="color:{_TEXT_3};">模型尚未训练，点击左侧按钮开始</span>',
                    unsafe_allow_html=True,
                )

        if train_clicked:
            try:
                with st.spinner("正在训练模型..."):
                    model_metrics = salary_predictor.train()
                st.success("模型训练完成并已保存。")

                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("R²", f"{model_metrics['r2']:.4f}")
                mc2.metric("MAE (K)", f"{model_metrics['mae']:.2f}")
                mc3.metric("RMSE (K)", f"{model_metrics['rmse']:.2f}")

                if salary_predictor.is_trained:
                    importance = salary_predictor.get_feature_importance(top_n=10)
                    df_imp = pd.DataFrame(importance)
                    fig_imp = px.bar(
                        df_imp, x="importance", y="feature", orientation="h",
                        color="importance",
                        color_continuous_scale=[_CHART_BLUES[1], _CHART_BLUES[2], _CHART_BLUES[4]],
                    )
                    fig_imp = _apply_chart_style(fig_imp, title="特征重要性 Top 10", height=400)
                    fig_imp.update_layout(showlegend=False, coloraxis_showscale=False)
                    st.plotly_chart(fig_imp, width='stretch', config={"displayModeBar": False})
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"训练失败: {exc}")

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Tab3: 薪资预测 ──
    with tab3:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("##### 在线薪资预测")
        if not salary_predictor.is_trained:
            try:
                salary_predictor.load_model()
            except FileNotFoundError:
                st.info("请先在「模型训练」标签页中训练模型。")

        with st.form("salary_predict_form"):
            title = st.text_input(
                "职位标题", value="Python高级开发工程师",
                placeholder="如：Python高级开发工程师",
                help="输入完整职位标题，用于提取职级和关键词特征"
            )
            c1, c2 = st.columns(2)
            city = c1.text_input("城市", value="北京", placeholder="如：北京")
            experience = c1.selectbox(
                "经验要求",
                ["不限", "应届生", "1-3年", "3-5年", "5-10年", "10年以上"],
            )
            education = c2.selectbox(
                "学历要求",
                ["不限", "大专", "本科", "硕士", "博士"],
            )
            skills_text = st.text_input(
                "技能标签（逗号分隔）",
                value="Python, MySQL, Django",
                placeholder="如：Python, SQL, 机器学习",
            )

            col_submit, _ = st.columns([1, 3])
            with col_submit:
                submitted = st.form_submit_button("预测薪资", type="primary", width='stretch')

        if submitted and salary_predictor.is_trained:
            skills = [s.strip() for s in skills_text.split(",") if s.strip()]
            result = salary_predictor.predict({
                "title": title, "city": city,
                "experience": experience, "education": education,
                "skills": skills,
            })
            st.markdown(f"""
            <div style="background:{_PRIMARY_SUBTLE}; border-radius:{_RADIUS};
                        padding:28px 32px; margin-top:20px; text-align:center;">
                <div style="font-size:0.82rem; color:{_TEXT_3}; margin-bottom:6px;">预测薪资中位数</div>
                <div style="font-size:2.6rem; font-weight:600; color:{_PRIMARY};
                            letter-spacing:-0.02em; line-height:1.2;">
                    {result['salary_mid']}
                    <span style="font-size:0.9rem; font-weight:400; color:{_TEXT_2};"> K/月</span>
                </div>
                <div style="font-size:0.82rem; color:{_TEXT_3}; margin-top:8px;">
                    参考区间 {result['salary_min']} ~ {result['salary_max']} K/月
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# 页面：技能分析
# ============================================================================

def page_skills(jobs: list[dict[str, Any]]) -> None:
    """技能分析：频率、共现、关联规则与趋势。"""
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">技能分析</div>
        <div class="page-subtitle">基于 jieba 分词 + TF-IDF 的技术栈挖掘，揭示市场技能需求趋势</div>
    </div>
    """, unsafe_allow_html=True)

    if not jobs:
        st.info("暂无数据。")
        return

    tab1, tab2, tab3 = st.tabs(["技能频率", "共现分析", "趋势与关联"])

    with tab1:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        freq = skill_analyzer.get_skills_frequency(top_n=20)
        if not freq:
            st.info("未能提取技能关键词。")
        else:
            df = pd.DataFrame(freq.most_common(), columns=["技能", "频次"])
            fig = px.bar(
                df, x="频次", y="技能", orientation="h",
                color="频次",
                color_continuous_scale=[_CHART_BLUES[1], _CHART_BLUES[2], _CHART_BLUES[4]],
            )
            fig = _apply_chart_style(fig, title="技能出现频率 Top 20", height=520)
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        co = skill_analyzer.get_skill_cooccurrence(top_n=15)
        if not co:
            st.info("共现数据不足。")
        else:
            rows = [
                {"技能 A": pair[0], "技能 B": pair[1], "共现次数": count}
                for pair, count in co.most_common()
            ]
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        c_left, c_right = st.columns(2)

        with c_left:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            trending = skill_analyzer.get_trending_skills(top_n=10)
            if trending:
                df_trend = pd.DataFrame(trending)
                fig_t = px.bar(
                    df_trend, x="score", y="skill", orientation="h",
                    color="score",
                    color_continuous_scale=[_CHART_GREENS[1], _CHART_GREENS[2], _CHART_GREENS[4]],
                )
                fig_t = _apply_chart_style(fig_t, title="趋势技能综合评分 Top 10", height=400)
                fig_t.update_layout(showlegend=False, coloraxis_showscale=False)
                st.plotly_chart(fig_t, width='stretch', config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

        with c_right:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            rules = skill_analyzer.analyze_skill_associations(min_support=0.01, top_n=10)
            if rules:
                st.markdown("##### 技能关联规则 Top 10")
                st.dataframe(pd.DataFrame(rules), width='stretch', hide_index=True)
            else:
                st.info("关联规则数据不足。")
            st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# 页面：岗位推荐
# ============================================================================

def page_recommend(jobs: list[dict[str, Any]]) -> None:
    """岗位推荐：基于职位或用户画像的相似推荐。"""
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">岗位推荐</div>
        <div class="page-subtitle">TF-IDF 文本向量 + 技能多热向量融合，余弦相似度智能匹配</div>
    </div>
    """, unsafe_allow_html=True)

    if not jobs:
        st.info("暂无职位数据。")
        return

    job_recommender.refresh_index()

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    mode = st.radio(
        "推荐模式",
        ["基于已有职位推荐", "基于用户画像推荐"],
        horizontal=True,
    )

    if mode == "基于已有职位推荐":
        job_options = {
            f"[{j.get('id')}] {j.get('title')} - {j.get('company')}": j.get("id")
            for j in jobs if j.get("id") is not None
        }
        if not job_options:
            st.info("无有效职位 ID。")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            selected = st.selectbox("选择参考职位", list(job_options.keys()))
        with c2:
            top_n = st.slider("推荐数量", 3, 20, 10)
        with c3:
            sort_by = st.selectbox(
                "排序方式",
                ["composite", "similarity", "salary", "city"],
                format_func=lambda x: {
                    "composite": "综合得分", "similarity": "相似度",
                    "salary": "薪资优先", "city": "城市优先",
                }[x],
            )

        if st.button("获取推荐", type="primary"):
            job_id = job_options[selected]
            results = job_recommender.recommend_for_job(
                int(job_id), top_n=top_n, sort_by=sort_by,  # type: ignore[arg-type]
            )
            _render_recommend_results(results)

    else:
        with st.form("profile_form"):
            c1, c2 = st.columns(2)
            title = c1.text_input("意向岗位", "Python 开发工程师")
            city = c2.text_input("期望城市", "北京")
            skills_text = st.text_input("技能标签", "Python, Django, MySQL")
            c3, c4, c5 = st.columns(3)
            min_sal = c3.number_input("最低薪资 (K)", 10.0, 100.0, 20.0)
            max_sal = c4.number_input("最高薪资 (K)", 10.0, 100.0, 35.0)
            top_n = c5.slider("推荐数量", 3, 20, 10)
            submitted = st.form_submit_button("推荐岗位", type="primary", width='stretch')

        if submitted:
            skills = [s.strip() for s in skills_text.split(",") if s.strip()]
            results = job_recommender.recommend_for_profile(
                {"skills": skills, "city": city, "preferred_city": city,
                 "min_salary": min_sal, "max_salary": max_sal, "title": title},
                top_n=top_n,
            )
            _render_recommend_results(results)

    st.markdown('</div>', unsafe_allow_html=True)


def _render_recommend_results(results: list[dict[str, Any]]) -> None:
    """渲染推荐结果列表。"""
    if not results:
        st.info("未找到匹配的推荐岗位。")
        return

    st.markdown(f"##### 为您找到 {len(results)} 个推荐岗位")

    rows = []
    for item in results:
        job = item["job"]
        rows.append({
            "职位": job.get("title"),
            "公司": job.get("company"),
            "城市": job.get("city"),
            "相似度": f"{item['similarity']:.2%}",
            "综合得分": item["composite_score"],
            "薪资(K)": item.get("salary_mid") or "—",
        })
    st.dataframe(
        pd.DataFrame(rows), width='stretch', hide_index=True,
        column_config={
            "相似度": st.column_config.ProgressColumn(
                "相似度", format="%.0f%%", min_value=0.0, max_value=1.0,
            ),
        },
    )


# ============================================================================
# 页面：数据管理
# ============================================================================

def page_data_management() -> None:
    """数据管理：搜索筛选、查看、清洗与示例数据导入。"""
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">数据管理</div>
        <div class="page-subtitle">智能搜索筛选职位数据，支持关键词、城市、经验、薪资区间等多维度过滤</div>
    </div>
    """, unsafe_allow_html=True)

    jobs = load_jobs()

    # ── 搜索筛选区 ──
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("##### 🔍 智能搜索筛选")

    col_kw, col_city, col_exp = st.columns(3)
    with col_kw:
        keyword = st.text_input(
            "关键词搜索",
            placeholder="输入职位、公司、技能关键词...",
            help="搜索范围：职位标题、公司名称、技能标签、职位描述"
        )
    with col_city:
        all_cities = sorted(set(
            str(j.get("city", "")).replace("市", "")
            for j in jobs if j.get("city") and j["city"] != "未知"
        ))
        city_options = ["全部"] + all_cities
        city_select = st.selectbox("城市", city_options)
    with col_exp:
        all_exp = sorted(set(
            j.get("experience") for j in jobs
            if j.get("experience") is not None
        ))
        exp_options = ["全部"] + all_exp
        exp_select = st.selectbox("经验要求", exp_options)

    col_sal1, col_sal2, col_info = st.columns(3)
    with col_sal1:
        sal_min = st.number_input("最低薪资 (K/月)", min_value=0.0, value=0.0, step=1.0)
    with col_sal2:
        sal_max = st.number_input("最高薪资 (K/月)", min_value=0.0, value=100.0, step=1.0)
    with col_info:
        # 实时显示筛选结果数
        filtered = filter_jobs(
            jobs, keyword=keyword, city=city_select,
            experience=exp_select,
            salary_min=sal_min if sal_min > 0 else None,
            salary_max=sal_max if sal_max < 100 else None,
        )
        has_salary = sum(1 for j in filtered if j.get("salary_min") and j["salary_min"] > 0)
        st.markdown(f"""
        <div style="text-align:center; padding-top:8px;">
            <div style="font-size:2rem; font-weight:600; color:#5B8DEF;">{len(filtered)}</div>
            <div style="font-size:0.75rem; color:#8E8E93;">筛选结果</div>
            <div style="font-size:0.7rem; color:#AEAEB2;">{has_salary} 条有薪资</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── 操作区 ──
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("##### 数据清洗")
        st.caption("标准化薪资、城市、技能等字段")
        if st.button("执行数据清洗", type="primary", width='stretch'):
            try:
                with st.spinner("正在清洗数据..."):
                    stats = data_cleaner.clean_all()
                clear_jobs_cache()
                job_recommender.refresh_index()
                st.success(
                    f"处理 {stats['processed']} 条 | 新增 {stats['added']} | 更新 {stats['updated']}"
                )
            except Exception as exc:
                st.error(f"清洗失败: {exc}")

    with c2:
        st.markdown("##### 示例数据")
        st.caption("快速导入 5 条演示职位")
        if st.button("导入示例数据", width='stretch'):
            _seed_sample_jobs()
            clear_jobs_cache()
            job_recommender.refresh_index()
            st.success("示例数据已导入")
            st.rerun()

    with c3:
        st.markdown("##### 数据库信息")
        st.caption(f"类型 `{settings.database.backend.upper()}`")
        st.caption(f"库名 `{settings.database.mysql_database}`")
        st.caption(f"地址 `{settings.database.mysql_host}:{settings.database.mysql_port}`")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── 筛选结果表格 ──
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown(f"##### 职位数据（总 {len(jobs)} 条，筛选 {len(filtered)} 条）")

    if filtered:
        df = pd.DataFrame(filtered)
        display_cols = [
            c for c in ["title", "company", "city", "salary_min", "salary_max",
                        "experience", "education", "source"]
            if c in df.columns
        ]
        # 格式化薪资列
        if "salary_min" in df.columns:
            df["薪资(K)"] = df.apply(
                lambda r: f"{r.get('salary_min', '-')}~{r.get('salary_max', '-')}"
                if r.get("salary_min") and r.get("salary_max") and r["salary_min"] > 0
                else "面议", axis=1
            )
        st.dataframe(df[display_cols], width='stretch', hide_index=True)
    else:
        st.info("没有匹配的职位数据，请调整筛选条件。")
    st.markdown('</div>', unsafe_allow_html=True)


def _seed_sample_jobs() -> None:
    """写入一批示例职位数据。"""
    samples = [
        {
            "title": "Python 后端工程师", "company": "星云科技", "city": "北京",
            "industry": "互联网", "source": "boss",
            "experience": "3-5年", "education": "本科",
            "skills": ["Python", "Django", "MySQL", "Redis"],
            "salary_min": 25, "salary_max": 40,
            "description": "负责后端 API 开发，熟悉 Python 与 Django。",
            "url": "https://example.com/jobs/101",
        },
        {
            "title": "Python 数据分析师", "company": "数澜信息", "city": "上海",
            "industry": "金融", "source": "lagou",
            "experience": "1-3年", "education": "硕士",
            "skills": ["Python", "Pandas", "机器学习", "SQL"],
            "salary_min": 20, "salary_max": 35,
            "description": "数据分析与机器学习建模。",
            "url": "https://example.com/jobs/102",
        },
        {
            "title": "Java 开发工程师", "company": "云帆软件", "city": "深圳",
            "industry": "互联网", "source": "boss",
            "experience": "3-5年", "education": "本科",
            "skills": ["Java", "Spring Boot", "MySQL"],
            "salary_min": 22, "salary_max": 38,
            "description": "Java 微服务开发。",
            "url": "https://example.com/jobs/103",
        },
        {
            "title": "前端开发工程师", "company": "前端工场", "city": "杭州",
            "industry": "电商", "source": "boss",
            "experience": "1-3年", "education": "本科",
            "skills": ["Vue", "JavaScript", "TypeScript"],
            "salary_min": 18, "salary_max": 30,
            "description": "Vue 前端开发。",
            "url": "https://example.com/jobs/104",
        },
        {
            "title": "算法工程师", "company": "智算科技", "city": "北京",
            "industry": "人工智能", "source": "lagou",
            "experience": "3-5年", "education": "硕士",
            "skills": ["Python", "PyTorch", "深度学习", "NLP"],
            "salary_min": 35, "salary_max": 60,
            "description": "大模型与 NLP 算法研发。",
            "url": "https://example.com/jobs/105",
        },
    ]
    for job in samples:
        db_manager.add_job(job)


# ============================================================================
# 页面：AI 智能报告
# ============================================================================

def page_ai_report(jobs: list[dict[str, Any]]) -> None:
    """AI 智能报告 — 支持直接输入 API Key 启用大模型深度分析。"""
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">AI 智能报告</div>
        <div class="page-subtitle">自动汇总平台数据，填入大模型 API Key 即可生成深度智能分析报告</div>
    </div>
    """, unsafe_allow_html=True)

    # ── API Key 配置区 ──
    if "ai_api_key" not in st.session_state:
        st.session_state.ai_api_key = ""
    if "ai_api_provider" not in st.session_state:
        st.session_state.ai_api_provider = "siliconflow"

    with st.expander("API 配置（粘贴 Key 即可启用 AI 深度分析）", expanded=not is_ai_available()):
        c1, c2 = st.columns([3, 1])
        with c1:
            api_key = st.text_input(
                "API Key",
                value=st.session_state.ai_api_key,
                type="password",
                placeholder="粘贴你的 API Key，如 sk-xxxxxxxx",
                help="支持硅基流动、DeepSeek、OpenAI 等平台的 API Key"
            )
        with c2:
            provider = st.selectbox(
                "平台",
                ["siliconflow", "deepseek", "openai", "gemini"],
                index=0,
                help="API Key 对应的平台"
            )

        if api_key and api_key != st.session_state.ai_api_key:
            st.session_state.ai_api_key = api_key
            st.session_state.ai_api_provider = provider
            import os
            os.environ["AI_API_PROVIDER"] = provider
            os.environ["AI_API_KEY"] = api_key
            st.success(f"API Key 已设置，平台: {provider}")
            st.rerun()

        if st.session_state.ai_api_key:
            st.caption(
                f"当前平台: **{get_provider_name()}** "
                f"| Key: {st.session_state.ai_api_key[:8]}..."
            )
        else:
            st.caption("未配置 API Key，将使用本地模板引擎。")
            st.markdown("""
            **免费获取 API Key：**
            - [硅基流动](https://siliconflow.cn) — 手机号注册即送额度（推荐）
            - [DeepSeek](https://platform.deepseek.com) — 手机号注册有免费额度
            """)

    # ── 生成按钮 ──
    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)

    c_btn, c_info = st.columns([1, 3])
    with c_btn:
        gen_clicked = st.button("生成报告", type="primary", width='stretch')
    with c_info:
        if is_ai_available():
            st.caption(f"将使用 **{get_provider_name()}** 大模型生成深度分析。")
        else:
            st.caption("将使用本地模板引擎生成基础报告。填入 API Key 可启用 AI 深度分析。")

    if gen_clicked:
        with st.spinner("正在汇总分析结果..."):
            report = _build_ai_report(jobs)

        # 如果配置了 AI API，额外生成 AI 深度分析
        if is_ai_available():
            with st.spinner("正在调用 AI 模型生成深度分析..."):
                try:
                    stats = collect_report_stats(jobs)
                    collect_skill_stats(stats)
                    collect_model_stats(stats)
                    ai_section = generate_ai_report(stats)
                    if ai_section:
                        report += "\n\n---\n\n## 五、AI 深度分析\n\n"
                        report += f"> 以下内容由 **{get_provider_name()}** 大模型自动生成\n\n"
                        report += ai_section
                except Exception as exc:
                    st.warning(f"AI 分析生成失败（不影响基础报告）: {exc}")

        st.markdown('<div class="report-box">', unsafe_allow_html=True)
        st.markdown(report)
        st.markdown('</div>', unsafe_allow_html=True)

        st.download_button(
            "下载报告 (Markdown)",
            data=report,
            file_name=f"招聘分析报告_{datetime.now():%Y%m%d_%H%M}.md",
            mime="text/markdown",
            type="primary",
        )

    if not gen_clicked:
        st.markdown("""
        <div class="guide-card">
            <p>点击上方「生成报告」按钮生成结构化分析报告。
            填入大模型 API Key 后，系统将额外调用 AI 进行深度市场洞察分析。</p>
        </div>
        """, unsafe_allow_html=True)


def _build_ai_report(jobs: list[dict[str, Any]]) -> str:
    """数据驱动的 Markdown 分析报告，所有结论从实际数据中计算得出。"""
    metrics = compute_overview_metrics(jobs)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# 招聘数据分析报告",
        f"",
        f"> 生成时间: {now_str}  ",
        f"> 数据库引擎: `{settings.database.backend.upper()}`  ",
        f"> 职位总数: {metrics['total_jobs']}  ",
        f"",
        f"---",
        f"",
        f"## 一、数据全景",
        f"",
        f"| 指标 | 数值 | 说明 |",
        f"|------|------|------|",
        f"| 总职位数 | {metrics['total_jobs']} | 全平台累计采集 |",
        f"| 平均月薪 | {metrics['avg_salary']} K | 所有有薪资数据的职位均值 |",
        f"| 第一热门城市 | {metrics['top_city']} | 职位数量最多 |",
        f"| 第一热门技能 | {metrics['top_skill']} | 出现频率最高 |",
        f"",
    ]

    # ---- 城市分布分析 ----
    city_counts = Counter(
        str(j.get("city") or "未知") for j in jobs
    )
    top_cities = city_counts.most_common(5)
    if top_cities:
        lines.append("### 城市分布 TOP 5")
        lines.append("")
        lines.append("| 城市 | 职位数 | 占比 |")
        lines.append("|------|--------|------|")
        total = max(city_counts.total(), 1)
        for city, cnt in top_cities:
            pct = cnt / total * 100
            lines.append(f"| {city} | {cnt} | {pct:.1f}% |")
        lines.append("")

    # ---- 薪资分析 ----
    salaries = []
    for j in jobs:
        mid = _salary_mid(j)
        if mid is not None:
            salaries.append(mid)
    if salaries:
        salaries.sort()
        p25 = salaries[len(salaries) // 4]
        p50 = salaries[len(salaries) // 2]
        p75 = salaries[len(salaries) * 3 // 4]
        avg_sal = sum(salaries) / len(salaries)
        lines.append("### 薪资分布")
        lines.append("")
        lines.append("| 指标 | 数值 (K/月) |")
        lines.append("|------|-------------|")
        lines.append(f"| 最低 | {min(salaries):.1f} |")
        lines.append(f"| 25分位 | {p25:.1f} |")
        lines.append(f"| 中位数 | {p50:.1f} |")
        lines.append(f"| 75分位 | {p75:.1f} |")
        lines.append(f"| 最高 | {max(salaries):.1f} |")
        lines.append(f"| 平均 | {avg_sal:.1f} |")
        lines.append("")

        # 经验-薪资关系
        exp_salary: dict[str, list[float]] = {}
        for j in jobs:
            exp = j.get("experience")
            mid = _salary_mid(j)
            if exp and mid:
                exp_salary.setdefault(str(exp), []).append(mid)
        if len(exp_salary) > 1:
            lines.append("### 经验与薪资关系")
            lines.append("")
            lines.append("| 经验要求 | 平均薪资 (K/月) | 样本数 |")
            lines.append("|----------|----------------|--------|")
            for exp in ["应届生", "1年以内", "1-3年", "3-5年", "5-10年", "10年以上"]:
                vals = exp_salary.get(exp, [])
                if vals:
                    lines.append(f"| {exp} | {sum(vals)/len(vals):.1f} | {len(vals)} |")
            lines.append("")

    # ---- 技能洞察 ----
    if jobs:
        freq = skill_analyzer.get_skills_frequency(top_n=10)
        if freq:
            lines.append("## 二、技能市场洞察")
            lines.append("")
            lines.append("### 高频技能 TOP 10")
            lines.append("")
            lines.append("| 排名 | 技能 | 出现次数 |")
            lines.append("|------|------|----------|")
            for rank, (skill, count) in enumerate(freq.most_common(10), 1):
                lines.append(f"| {rank} | **{skill}** | {count} |")
            lines.append("")

            # 技能组合分析
            top_skills = [s for s, _ in freq.most_common(15)]
            pairs = skill_analyzer.analyze_skill_associations(min_support=0.01, top_n=8)
            if pairs:
                lines.append("### 技能共现关系（强关联）")
                lines.append("")
                lines.append("| 技能组合 | 支持度 | 置信度 | 提升度 |")
                lines.append("|----------|--------|--------|--------|")
                for pair in pairs[:8]:
                    lines.append(
                        f"| {pair['antecedent']} + {pair['consequent']} "
                        f"| {pair['support']:.2%} "
                        f"| {pair['confidence']:.2%} "
                        f"| {pair['lift']:.1f}x |"
                    )
                lines.append("")

        # 趋势技能
        trending = skill_analyzer.get_trending_skills(top_n=8)
        if trending:
            lines.append("### 上升趋势技能")
            lines.append("")
            for item in trending:
                direction = "↗" if item['score'] > 0.5 else "→"
                lines.append(
                    f"- {direction} **{item['skill']}** "
                    f"— 近期 {item['recent_count']} 条，趋势评分 {item['score']:.2f}"
                )
            lines.append("")

    # ---- 薪资模型 ----
    if salary_predictor.is_trained or _try_load_model():
        lines.append("## 三、薪资预测模型 (XGBoost v2)")
        lines.append("")
        if salary_predictor.metrics:
            m = salary_predictor.metrics
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            lines.append(f"| R² (决定系数) | {m.get('r2', 0):.4f} |")
            lines.append(f"| MAE (平均绝对误差) | {m.get('mae', 0):.2f} K/月 |")
            lines.append(f"| RMSE (均方根误差) | {m.get('rmse', 0):.2f} K/月 |")
            lines.append(f"| 训练样本数 | {int(m.get('train_size', 0))} |")
            lines.append(f"| 特征维度 | {m.get('n_features', '-')} |")
            if m.get('cv_mae_mean', 0) > 0:
                lines.append(f"| 交叉验证 MAE | {m['cv_mae_mean']:.2f} ± {m['cv_mae_std']:.2f} K/月 |")
            lines.append("")

            # 特征重要性
            try:
                importance = salary_predictor.get_feature_importance(top_n=8)
                if importance:
                    lines.append("### 关键影响因素")
                    lines.append("")
                    for fi in importance:
                        name = fi['feature'].replace('tfidf_', '').replace('skill_', '')
                        lines.append(f"- **{name}**: 权重 {fi['importance']:.4f}")
                    lines.append("")
            except Exception:
                pass

    # ---- 数据驱动建议 ----
    lines.append("## 四、数据洞察与建议")
    lines.append("")

    insight_num = 1

    # 城市集中度
    if city_counts:
        top1_pct = city_counts.most_common(1)[0][1] / max(city_counts.total(), 1) * 100
        if top1_pct > 50:
            lines.append(f"{insight_num}. **城市集中度高**：{city_counts.most_common(1)[0][0]} "
                         f"占全部职位的 {top1_pct:.0f}%，建议关注其他城市的市场机会。")
            insight_num += 1

    # 薪资跨度
    if salaries and len(salaries) > 10:
        span = max(salaries) - min(salaries)
        if span > 50:
            lines.append(f"{insight_num}. **薪资跨度大**：最低 {min(salaries):.0f}K 到最高 "
                         f"{max(salaries):.0f}K，差距 {span:.0f}K。"
                         f"中位数 {p50:.0f}K 可作为定薪参考基准。")
            insight_num += 1

    # 技能趋势
    if trending:
        hot_skills = [t['skill'] for t in trending[:3]]
        lines.append(f"{insight_num}. **热门技能方向**：{', '.join(hot_skills)} "
                     f"呈上升趋势，建议团队重点关注这些技术栈的储备。")
        insight_num += 1

    # 模型评估
    if salary_predictor.is_trained and salary_predictor.metrics:
        r2 = salary_predictor.metrics.get('r2', 0)
        mae = salary_predictor.metrics.get('mae', 0)
        if r2 > 0.3:
            lines.append(f"{insight_num}. **薪资模型可用**：R²={r2:.2f}，MAE={mae:.1f}K/月。"
                         f"可用于新职位的薪资区间预估，辅助招聘定价决策。")
            insight_num += 1

    # 数据质量
    quality_issues = []
    unknown_city = sum(1 for j in jobs if j.get("city") == "未知")
    no_exp = sum(1 for j in jobs if j.get("experience") is None)
    no_salary = sum(1 for j in jobs if not (j.get("salary_min") and j["salary_min"] > 0))
    if unknown_city > len(jobs) * 0.3:
        quality_issues.append(f"城市信息缺失 {unknown_city} 条")
    if no_exp > len(jobs) * 0.3:
        quality_issues.append(f"经验信息缺失 {no_exp} 条")
    if no_salary > len(jobs) * 0.5:
        quality_issues.append(f"薪资信息缺失 {no_salary} 条")
    if quality_issues:
        lines.append(f"{insight_num}. **数据质量提示**：{'、'.join(quality_issues)}。"
                     f"建议扩大爬取范围并启用详情页抓取以提升数据完整度。")
        insight_num += 1

    if insight_num == 1:
        lines.append("数据量尚不足以生成统计显著的建议，请继续扩充数据。")

    lines.extend([
        "",
        "---",
        "",
        f"*报告由招聘数据分析平台自动生成 | {now_str}*",
        "",
        "> 本报告所有数据来源于平台数据库，分析结论由内置模块（技能NLP、薪资XGBoost模型、岗位推荐引擎）驱动。",
        "> 后续可接入大语言模型 API 以生成更具洞察深度和叙述性的自然语言分析。",
    ])
    return "\n".join(lines)

def _try_load_model() -> bool:
    """尝试加载已保存的薪资模型。"""
    try:
        salary_predictor.load_model()
        return True
    except FileNotFoundError:
        return False


# ============================================================================
# 主入口
# ============================================================================

def main() -> None:
    """应用主入口：注入全局样式 → 侧边栏导航 → 页面路由。"""
    _inject_global_css()
    page = render_sidebar()
    jobs = load_jobs()

    if page == "首页概览":
        page_overview(jobs)
    elif page == "薪资分析":
        page_salary(jobs)
    elif page == "技能分析":
        page_skills(jobs)
    elif page == "岗位推荐":
        page_recommend(jobs)
    elif page == "数据管理":
        page_data_management()
    elif page == "AI智能报告":
        page_ai_report(jobs)


if __name__ == "__main__":
    main()
