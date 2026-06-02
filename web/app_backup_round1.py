"""
招聘数据分析平台 — Streamlit 主入口（UI/UX 全面优化版）。

多页面应用，集成数据清洗、技能 NLP、薪资预测与岗位推荐等分析能力。
运行方式（在项目根目录）::

    streamlit run web/app.py

优化内容：
  - 现代化 B 端数据大屏设计风格（主色 #165DFF）
  - 全局 CSS 注入：卡片阴影、圆角、间距统一
  - 侧边栏图标导航 + 系统状态面板
  - 自定义指标卡片（渐变背景 + 图标 + 趋势标识）
  - Plotly 统一主题模板（配色 / 字体 / 网格线）
  - 响应式宽屏布局 + 卡片式内容区域
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
from analysis.salary_predictor import salary_predictor
from analysis.skill_nlp import skill_analyzer
from config.settings import BASE_DIR, settings
from storage.database import db_manager

# ============================================================================
# 全局设计系统
# ============================================================================

# 品牌色板
_PRIMARY = "#165DFF"          # 主色 — 深蓝
_PRIMARY_LIGHT = "#3C7EFF"    # 浅蓝
_PRIMARY_SOFT = "#E8F0FE"     # 极浅蓝（背景）
_ACCENT = "#0FC6C2"           # 青绿强调
_ACCENT_SOFT = "#E6FAF9"      # 极浅青
_BG_PAGE = "#F5F7FA"          # 页面底色
_BG_CARD = "#FFFFFF"          # 卡片底色
_TEXT_1 = "#1D2129"           # 主文字
_TEXT_2 = "#4E5969"           # 次文字
_TEXT_3 = "#86909C"           # 辅助文字
_BORDER = "#E5E6EB"           # 边框
_SHADOW_CARD = "0 2px 12px rgba(0,0,0,0.06)"
_SHADOW_HOVER = "0 4px 20px rgba(22,93,255,0.12)"
_RADIUS = "12px"

# 导航页面列表（含图标）
_NAV_ITEMS: list[dict[str, str]] = [
    {"label": "首页概览",  "icon": "🏠", "desc": "平台数据总览"},
    {"label": "薪资分析",  "icon": "💰", "desc": "训练模型与预测"},
    {"label": "技能分析",  "icon": "🧠", "desc": "NLP 技能挖掘"},
    {"label": "岗位推荐",  "icon": "🎯", "desc": "智能匹配推荐"},
    {"label": "数据管理",  "icon": "🗄️", "desc": "清洗与维护"},
    {"label": "AI智能报告","icon": "📋", "desc": "自动生成报告"},
]
_NAV_PAGES: list[str] = [item["label"] for item in _NAV_ITEMS]

# 图表配色方案
_CHART_COLORS = ["#165DFF", "#0FC6C2", "#FF7D00", "#F53F3F", "#722ED1", "#14C9C9",
                 "#3491FA", "#F7BA1E", "#00B42A", "#FF5722", "#9FDB1D", "#D91AAD"]
_CHART_BLUES = ["#E8F0FE", "#BEDAFF", "#7EB5FF", "#4C94FF", "#165DFF"]
_CHART_GREENS = ["#E6FAF9", "#B2F0EC", "#5EE6DF", "#2DD4CB", "#0FC6C2"]


# ============================================================================
# 全局样式注入
# ============================================================================

def _inject_global_css() -> None:
    """注入全局自定义 CSS 样式表。"""
    st.markdown(f"""
    <style>
    /* ===== 根变量 ===== */
    :root {{
        --primary: {_PRIMARY};
        --primary-light: {_PRIMARY_LIGHT};
        --primary-soft: {_PRIMARY_SOFT};
        --accent: {_ACCENT};
        --bg-page: {_BG_PAGE};
        --bg-card: {_BG_CARD};
        --text-1: {_TEXT_1};
        --text-2: {_TEXT_2};
        --text-3: {_TEXT_3};
        --border: {_BORDER};
        --radius: {_RADIUS};
        --shadow-card: {_SHADOW_CARD};
    }}

    /* ===== 全局背景 ===== */
    .stApp {{
        background: {_BG_PAGE};
    }}

    /* ===== 主内容区内边距 ===== */
    .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}

    /* ===== 侧边栏美化 ===== */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0D1B3E 0%, #132550 40%, #1A2D5A 100%);
        border-right: none;
    }}
    [data-testid="stSidebar"] * {{
        color: #E8ECF2 !important;
    }}
    [data-testid="stSidebar"] .stRadio label {{
        font-size: 14px !important;
        padding: 10px 14px !important;
        border-radius: 8px !important;
        margin-bottom: 4px !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
    }}
    [data-testid="stSidebar"] .stRadio label:hover {{
        background: rgba(255,255,255,0.08) !important;
    }}
    [data-testid="stSidebar"] .stRadio label:has(input:checked) {{
        background: {_PRIMARY} !important;
        color: #FFF !important;
        font-weight: 600 !important;
    }}
    [data-testid="stSidebar"] .stRadio label:has(input:checked) * {{
        color: #FFF !important;
    }}

    /* ===== 按钮增强 ===== */
    .stButton > button {{
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 8px 20px !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.02em;
    }}
    .stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(22,93,255,0.3) !important;
    }}
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {_PRIMARY}, {_PRIMARY_LIGHT}) !important;
    }}

    /* ===== Tab 标签美化 ===== */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: transparent;
        border-bottom: 2px solid {_BORDER};
        padding-bottom: 0;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0 !important;
        padding: 10px 20px !important;
        font-weight: 500 !important;
        color: {_TEXT_2} !important;
        background: transparent !important;
        border: none !important;
        transition: all 0.2s;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: {_PRIMARY} !important;
        background: {_PRIMARY_SOFT} !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: {_PRIMARY} !important;
        border-bottom: 3px solid {_PRIMARY} !important;
        font-weight: 600 !important;
    }}

    /* ===== 表单美化 ===== */
    [data-testid="stForm"] {{
        background: {_BG_CARD};
        border: 1px solid {_BORDER};
        border-radius: {_RADIUS};
        padding: 28px 32px;
        box-shadow: {_SHADOW_CARD};
    }}
    [data-testid="stForm"] .stButton {{
        text-align: right;
    }}

    /* ===== dataframe 美化 ===== */
    [data-testid="stDataFrame"] {{
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid {_BORDER};
    }}

    /* ===== selectbox / slider / input ===== */
    .stSelectbox [data-baseweb="select"], .stTextInput input {{
        border-radius: 8px !important;
    }}

    /* ===== alert 美化 ===== */
    [data-testid="stAlert"] {{
        border-radius: 10px;
        border-left: 4px solid {_PRIMARY};
    }}

    /* ===== 滚动条 ===== */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-thumb {{
        background: #CDD0D6;
        border-radius: 3px;
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: #A8ADB7; }}

    /* ===== 隐藏 Streamlit 默认元素 ===== */
    #MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent !important; }}

    /* ===== 指标卡片容器（自定义 HTML） ===== */
    .metric-card {{
        background: {_BG_CARD};
        border-radius: {_RADIUS};
        padding: 22px 24px;
        box-shadow: {_SHADOW_CARD};
        border: 1px solid {_BORDER};
        transition: all 0.25s ease;
        position: relative;
        overflow: hidden;
    }}
    .metric-card:hover {{
        box-shadow: {_SHADOW_HOVER};
        transform: translateY(-2px);
    }}
    .metric-card .metric-icon {{
        font-size: 2rem;
        margin-bottom: 8px;
    }}
    .metric-card .metric-value {{
        font-size: 2rem;
        font-weight: 700;
        color: {_TEXT_1};
        line-height: 1.2;
    }}
    .metric-card .metric-label {{
        font-size: 0.85rem;
        color: {_TEXT_3};
        margin-top: 4px;
    }}
    .metric-card .metric-accent {{
        position: absolute;
        top: 0; right: 0;
        width: 80px; height: 80px;
        background: linear-gradient(135deg, {_PRIMARY_SOFT} 0%, transparent 70%);
        border-radius: 0 0 0 80px;
    }}

    /* ===== 内容卡片 ===== */
    .content-card {{
        background: {_BG_CARD};
        border-radius: {_RADIUS};
        padding: 24px 28px;
        box-shadow: {_SHADOW_CARD};
        border: 1px solid {_BORDER};
        margin-bottom: 20px;
    }}

    /* ===== 页面标题区 ===== */
    .page-hero {{
        margin-bottom: 24px;
        padding-bottom: 20px;
        border-bottom: 2px solid {_BORDER};
    }}
    .page-hero .page-title {{
        font-size: 1.6rem;
        font-weight: 700;
        color: {_TEXT_1};
        margin-bottom: 4px;
    }}
    .page-hero .page-subtitle {{
        font-size: 0.9rem;
        color: {_TEXT_3};
    }}

    /* ===== 体验说明卡片 ===== */
    .guide-card {{
        background: linear-gradient(135deg, {_PRIMARY_SOFT}, #F0F5FF);
        border: 1px solid #BFD4FF;
        border-radius: {_RADIUS};
        padding: 18px 22px;
        margin-bottom: 20px;
    }}
    .guide-card p {{ margin: 0; color: {_PRIMARY}; font-size: 0.9rem; }}

    /* ===== 下载报告区域 ===== */
    .report-box {{
        background: {_BG_CARD};
        border-radius: {_RADIUS};
        padding: 28px 32px;
        box-shadow: {_SHADOW_CARD};
        border: 1px solid {_BORDER};
    }}
    </style>
    """, unsafe_allow_html=True)


# ============================================================================
# 图表统一主题
# ============================================================================

def _chart_layout(
    title: str = "",
    height: int = 380,
    show_legend: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """返回统一的 Plotly 布局配置字典。"""
    return dict(
        title=dict(
            text=title,
            font=dict(size=15, color=_TEXT_1, family="PingFang SC, Microsoft YaHei, sans-serif"),
            x=0.02,
        ),
        height=height,
        showlegend=show_legend,
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            gridcolor=_BORDER,
            zeroline=False,
            title_font=dict(size=12, color=_TEXT_2),
            tickfont=dict(size=11, color=_TEXT_2),
        ),
        yaxis=dict(
            gridcolor=_BORDER,
            zeroline=False,
            title_font=dict(size=12, color=_TEXT_2),
            tickfont=dict(size=11, color=_TEXT_2),
        ),
        font=dict(family="PingFang SC, Microsoft YaHei, sans-serif", color=_TEXT_2),
        colorway=_CHART_COLORS,
        **kwargs,
    )


def _apply_chart_style(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    """对已创建的图表统一应用样式布局。"""
    fig.update_layout(**_chart_layout(title=title, height=height))
    # 对 bar/histogram 等 trace 统一配色
    if hasattr(fig, "update_traces"):
        fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
    return fig


# ============================================================================
# 自定义指标卡片
# ============================================================================

def _metric_card(icon: str, value: str, label: str, accent_color: str = _PRIMARY) -> None:
    """渲染一个自定义 CSS 指标卡片。"""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-accent" style="background:linear-gradient(135deg,{accent_color}18 0%,transparent 70%)"></div>
        <div class="metric-icon">{icon}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# 数据加载（缓存）
# ============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def load_jobs() -> list[dict[str, Any]]:
    """从数据库加载全部职位（缓存 60 秒）。"""
    return db_manager.get_all_jobs()


def clear_jobs_cache() -> None:
    """清除职位数据缓存。"""
    load_jobs.clear()


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
# 侧边栏
# ============================================================================

def render_sidebar() -> str:
    """
    渲染左侧导航栏（优化版）。

    Returns:
        当前选中的页面名称。
    """
    # ---- 品牌区 ----
    st.sidebar.markdown("""
    <div style="display:flex;align-items:center;gap:12px;padding:16px 8px 8px 8px;margin-bottom:8px;
                border-bottom:1px solid rgba(255,255,255,0.1);">
        <div style="width:38px;height:38px;border-radius:10px;
                    background:linear-gradient(135deg,#165DFF,#3C7EFF);
                    display:flex;align-items:center;justify-content:center;font-size:18px;">
            📊
        </div>
        <div>
            <div style="font-size:15px;font-weight:700;color:#FFF;line-height:1.3;">招聘分析平台</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.45);">Job Analytics Platform</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---- 数据库状态指示 ----
    db_label = settings.database.backend.upper()
    db_color = "#00B42A" if settings.database.backend == "mysql" else "#FF7D00"
    st.sidebar.markdown(f"""
    <div style="display:flex;align-items:center;gap:6px;padding:6px 12px;margin:0 8px 12px 8px;
                background:rgba(255,255,255,0.06);border-radius:8px;font-size:11px;">
        <span style="width:8px;height:8px;border-radius:50%;background:{db_color};display:inline-block;"></span>
        <span style="color:rgba(255,255,255,0.6);">数据库</span>
        <span style="color:#FFF;font-weight:600;margin-left:auto;">{db_label}</span>
    </div>
    """, unsafe_allow_html=True)

    if settings.debug:
        st.sidebar.warning("⚠️ 调试模式已开启")

    # ---- 导航菜单（带图标） ----
    st.sidebar.markdown(
        '<p style="font-size:11px;color:rgba(255,255,255,0.4);padding:0 14px;margin:12px 0 4px 0;'
        'text-transform:uppercase;letter-spacing:0.1em;">功能导航</p>',
        unsafe_allow_html=True,
    )

    # 构建带图标的 radio 选项
    nav_options = [f"{item['icon']}  {item['label']}" for item in _NAV_ITEMS]
    selected_display = st.sidebar.radio(
        "导航",
        nav_options,
        label_visibility="collapsed",
    )

    # 解析选中的页面名
    for item in _NAV_ITEMS:
        if selected_display.startswith(item["icon"]):
            selected_page = item["label"]
            break
    else:
        selected_page = _NAV_PAGES[0]

    # ---- 系统信息（折叠面板） ----
    st.sidebar.markdown(
        '<p style="font-size:11px;color:rgba(255,255,255,0.4);padding:0 14px;margin:16px 0 4px 0;'
        'text-transform:uppercase;letter-spacing:0.1em;">系统信息</p>',
        unsafe_allow_html=True,
    )

    # 用简洁的文本呈现
    st.sidebar.markdown(f"""
    <div style="font-size:11px;color:rgba(255,255,255,0.45);padding:4px 14px;line-height:1.8;">
        <div>项目路径 <span style="color:rgba(255,255,255,0.65);float:right;">job_analysis_platform</span></div>
        <div>数据库 <span style="color:rgba(255,255,255,0.65);float:right;">job_analysis</span></div>
    </div>
    """, unsafe_allow_html=True)

    # ---- 刷新按钮 ----
    st.sidebar.markdown('<div style="padding: 8px 10px;">', unsafe_allow_html=True)
    if st.sidebar.button("🔄 刷新数据缓存", use_container_width=True):
        clear_jobs_cache()
        job_recommender.refresh_index()
        st.sidebar.success("缓存已刷新")
        st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    # ---- 底部版本信息 ----
    st.sidebar.markdown(f"""
    <div style="position:fixed;bottom:20px;left:20px;font-size:10px;color:rgba(255,255,255,0.25);">
        v2.0 · Powered by Streamlit
    </div>
    """, unsafe_allow_html=True)

    return selected_page


# ============================================================================
# 页面：首页概览
# ============================================================================

def page_overview(jobs: list[dict[str, Any]]) -> None:
    """首页概览：关键指标卡片与基础图表。"""
    # ---- 页面标题区 ----
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">📊 首页概览</div>
        <div class="page-subtitle">平台数据总览与核心指标一览，实时掌握招聘市场动态</div>
    </div>
    """, unsafe_allow_html=True)

    metrics = compute_overview_metrics(jobs)

    # ---- 四列指标卡片（自定义 HTML） ----
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card("📋", str(metrics["total_jobs"]), "总职位数", _PRIMARY)
    with c2:
        _metric_card("💵", f"{metrics['avg_salary']} K", "平均月薪", _ACCENT)
    with c3:
        _metric_card("🏙️", metrics["top_city"], "热门城市", "#722ED1")
    with c4:
        _metric_card("⚡", metrics["top_skill"], "热门技能", "#FF7D00")

    if not jobs:
        st.markdown("""
        <div class="guide-card">
            <p>💡 暂无职位数据，请前往 <b>「数据管理」</b> 页面导入示例数据或启动爬虫采集真实数据。</p>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- 图表区域（卡片包裹） ----
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        city_counts = Counter(
            str(j.get("city") or "未知").replace("市", "") for j in jobs
        )
        df_city = pd.DataFrame(
            city_counts.most_common(10), columns=["城市", "职位数"]
        )
        fig_city = px.bar(
            df_city, x="城市", y="职位数",
            color="职位数",
            color_continuous_scale=[_CHART_BLUES[1], _CHART_BLUES[3], _CHART_BLUES[4]],
        )
        fig_city = _apply_chart_style(fig_city, title="城市职位分布 Top 10", height=380)
        fig_city.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_city, use_container_width=True, config={"displayModeBar": False})
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
            fig_sal.update_traces(marker_line_width=0)
            st.plotly_chart(fig_sal, use_container_width=True, config={"displayModeBar": False})
        else:
            st.warning("暂无有效薪资数据。")
        st.markdown('</div>', unsafe_allow_html=True)

    # ---- 来源分布 + 行业分布 ----
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
        fig_pie.update_traces(textposition="inside", textinfo="percent+label", hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        industry_counts = Counter(
            (j.get("industry") or "未知").strip() for j in jobs if (j.get("industry") or "").strip()
        )
        if industry_counts:
            df_ind = pd.DataFrame(industry_counts.most_common(8), columns=["行业", "数量"])
            fig_ind = px.bar(
                df_ind, x="数量", y="行业", orientation="h",
                color="数量",
                color_continuous_scale=[_CHART_GREENS[1], _CHART_GREENS[3], _CHART_GREENS[4]],
            )
            fig_ind = _apply_chart_style(fig_ind, title="行业分布 Top 8", height=340)
            fig_ind.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig_ind, use_container_width=True, config={"displayModeBar": False})
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
        <div class="page-title">💰 薪资分析</div>
        <div class="page-subtitle">基于随机森林模型的薪资区间预测，包含数据探索、模型训练与在线预测</div>
    </div>
    """, unsafe_allow_html=True)

    if len(jobs) < 10:
        st.markdown("""
        <div class="guide-card">
            <p>⚠️ 有效职位不足 <b>10 条</b>，请先在「数据管理」补充数据后再训练模型。</p>
        </div>
        """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📈 薪资分布", "🧪 模型训练", "🔮 薪资预测"])

    # ---- Tab1: 薪资分布 ----
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
            # 仅显示职位数较多的城市（避免箱线图过于拥挤）
            top_cities = df["城市"].value_counts().head(8).index.tolist()
            df_plot = df[df["城市"].isin(top_cities)]
            fig = px.box(
                df_plot, x="城市", y="薪资中位数 (K/月)", color="城市",
                color_discrete_sequence=_CHART_COLORS,
            )
            fig = _apply_chart_style(fig, title="各城市薪资箱线图 (K/月)", height=440)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("暂无薪资数据。")

    # ---- Tab2: 模型训练 ----
    with tab2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### 🧪 随机森林回归模型")

        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            train_clicked = st.button("🚀 开始训练", type="primary", use_container_width=True)
        with col_info:
            if salary_predictor.is_trained and salary_predictor.metrics:
                m = salary_predictor.metrics
                st.markdown(
                    f'<span style="color:{_ACCENT};font-weight:600;">✅ 模型已就绪</span>&nbsp;&nbsp;'
                    f'R²={m.get("r2",0):.4f} | MAE={m.get("mae",0):.2f}K | RMSE={m.get("rmse",0):.2f}K',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<span style="color:{_TEXT_3};">模型尚未训练，点击左侧按钮开始</span>',
                    unsafe_allow_html=True,
                )

        if train_clicked:
            try:
                with st.spinner("正在训练模型，请稍候..."):
                    model_metrics = salary_predictor.train(model_type="random_forest")
                st.success("✅ 模型训练完成并已保存到 data/models/ 目录。")

                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("R² 决定系数", f"{model_metrics['r2']:.4f}")
                mc2.metric("MAE 平均误差", f"{model_metrics['mae']:.2f} K")
                mc3.metric("RMSE 均方根误差", f"{model_metrics['rmse']:.2f} K")

                if salary_predictor.is_trained:
                    importance = salary_predictor.get_feature_importance(top_n=10)
                    df_imp = pd.DataFrame(importance)
                    fig_imp = px.bar(
                        df_imp, x="importance", y="feature", orientation="h",
                        color="importance",
                        color_continuous_scale=[_CHART_BLUES[1], _CHART_BLUES[3], _CHART_BLUES[4]],
                    )
                    fig_imp = _apply_chart_style(fig_imp, title="特征重要性 Top 10", height=400)
                    fig_imp.update_layout(showlegend=False, coloraxis_showscale=False)
                    st.plotly_chart(fig_imp, use_container_width=True, config={"displayModeBar": False})
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"训练失败: {exc}")

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Tab3: 薪资预测 ----
    with tab3:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### 🔮 在线薪资预测")
        if not salary_predictor.is_trained:
            try:
                salary_predictor.load_model()
            except FileNotFoundError:
                st.info("💡 请先在「模型训练」标签页中训练模型，或确保模型文件已存在。")

        with st.form("salary_predict_form"):
            c1, c2 = st.columns(2)
            city = c1.text_input("🏙️ 城市", value="北京", placeholder="如：北京")
            industry = c2.text_input("🏭 行业", value="互联网", placeholder="如：互联网")
            experience = c1.selectbox(
                "📅 经验要求",
                ["不限", "应届生", "1-3年", "3-5年", "5-10年", "10年以上"],
            )
            education = c2.selectbox(
                "🎓 学历要求",
                ["不限", "大专", "本科", "硕士", "博士"],
            )
            skills_text = st.text_input(
                "🛠️ 技能标签（逗号分隔）",
                value="Python, MySQL, Django",
                placeholder="如：Python, SQL, 机器学习",
            )

            col_submit, col_empty = st.columns([1, 3])
            with col_submit:
                submitted = st.form_submit_button("🔮 预测薪资", type="primary", use_container_width=True)

        if submitted and salary_predictor.is_trained:
            skills = [s.strip() for s in skills_text.split(",") if s.strip()]
            result = salary_predictor.predict({
                "city": city, "industry": industry,
                "experience": experience, "education": education,
                "skills": skills,
            })
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,{_PRIMARY_SOFT},#F0F5FF);
                        border-radius:12px;padding:20px 28px;margin-top:16px;
                        border:1px solid #BFD4FF;text-align:center;">
                <div style="font-size:0.85rem;color:{_TEXT_3};margin-bottom:4px;">预测薪资中位数</div>
                <div style="font-size:2.4rem;font-weight:800;color:{_PRIMARY};">{result['salary_mid']} <span style="font-size:1rem;font-weight:400;">K/月</span></div>
                <div style="font-size:0.85rem;color:{_TEXT_3};margin-top:6px;">
                    参考区间 <b>{result['salary_min']} ~ {result['salary_max']}</b> K/月
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
        <div class="page-title">🧠 技能分析</div>
        <div class="page-subtitle">基于 jieba 分词 + TF-IDF 的技术栈挖掘，揭示市场技能需求趋势</div>
    </div>
    """, unsafe_allow_html=True)

    if not jobs:
        st.info("暂无数据。")
        return

    tab1, tab2, tab3 = st.tabs(["📊 技能频率", "🔗 共现分析", "📈 趋势与关联"])

    with tab1:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        freq = skill_analyzer.get_skills_frequency(top_n=20)
        if not freq:
            st.warning("未能提取技能关键词。")
        else:
            df = pd.DataFrame(freq.most_common(), columns=["技能", "频次"])
            fig = px.bar(
                df, x="频次", y="技能", orientation="h",
                color="频次",
                color_continuous_scale=[_CHART_BLUES[1], _CHART_BLUES[2], _CHART_BLUES[4]],
            )
            fig = _apply_chart_style(fig, title="技能出现频率 Top 20", height=520)
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        co = skill_analyzer.get_skill_cooccurrence(top_n=15)
        if not co:
            st.warning("共现数据不足。")
        else:
            rows = [
                {"技能 A": pair[0], "技能 B": pair[1], "共现次数": count}
                for pair, count in co.most_common()
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
                st.plotly_chart(fig_t, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)

        with c_right:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            rules = skill_analyzer.analyze_skill_associations(min_support=0.01, top_n=10)
            if rules:
                st.markdown("##### 技能关联规则 Top 10")
                st.dataframe(pd.DataFrame(rules), use_container_width=True, hide_index=True)
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
        <div class="page-title">🎯 岗位推荐</div>
        <div class="page-subtitle">TF-IDF 文本向量 + 技能多热向量融合，余弦相似度智能匹配</div>
    </div>
    """, unsafe_allow_html=True)

    if not jobs:
        st.info("暂无职位数据。")
        return

    job_recommender.refresh_index()

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    mode = st.radio(
        "请选择推荐模式",
        ["📋 基于已有职位推荐", "👤 基于用户画像推荐"],
        horizontal=True,
    )

    if mode == "📋 基于已有职位推荐":
        job_options = {
            f"[{j.get('id')}] {j.get('title')} - {j.get('company')}": j.get("id")
            for j in jobs if j.get("id") is not None
        }
        if not job_options:
            st.warning("无有效职位 ID。")
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

        if st.button("🔍 获取推荐", type="primary"):
            job_id = job_options[selected]
            results = job_recommender.recommend_for_job(
                int(job_id), top_n=top_n, sort_by=sort_by,  # type: ignore[arg-type]
            )
            _render_recommend_results(results)

    else:
        with st.form("profile_form"):
            c1, c2 = st.columns(2)
            title = c1.text_input("💼 意向岗位", "Python 开发工程师")
            city = c2.text_input("📍 期望城市", "北京")
            skills_text = st.text_input("🛠️ 技能标签", "Python, Django, MySQL")
            c3, c4, c5 = st.columns(3)
            min_sal = c3.number_input("💰 最低薪资 (K)", 10.0, 100.0, 20.0)
            max_sal = c4.number_input("💰 最高薪资 (K)", 10.0, 100.0, 35.0)
            top_n = c5.slider("推荐数量", 3, 20, 10)
            submitted = st.form_submit_button("🎯 推荐岗位", type="primary", use_container_width=True)

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
    """渲染推荐结果列表（样式增强版）。"""
    if not results:
        st.warning("未找到匹配的推荐岗位。")
        return

    st.markdown(f"##### 🎯 为您找到 {len(results)} 个推荐岗位")

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
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 column_config={
                     "相似度": st.column_config.ProgressColumn(
                         "相似度", format="%.0f%%",
                         min_value=0.0, max_value=1.0,
                     ),
                 })


# ============================================================================
# 页面：数据管理
# ============================================================================

def page_data_management() -> None:
    """数据管理：查看、清洗与示例数据导入。"""
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">🗄️ 数据管理</div>
        <div class="page-subtitle">职位数据的清洗、导入与维护，确保分析数据质量</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- 操作按钮区 ----
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("##### 🧹 数据清洗")
        st.caption("标准化薪资、城市、技能等字段")
        if st.button("执行数据清洗", type="primary", use_container_width=True):
            try:
                with st.spinner("正在清洗数据..."):
                    stats = data_cleaner.clean_all()
                clear_jobs_cache()
                job_recommender.refresh_index()
                st.success(f"✅ 处理 {stats['processed']} 条 | 新增 {stats['added']} | 更新 {stats['updated']}")
            except Exception as exc:
                st.error(f"清洗失败: {exc}")

    with c2:
        st.markdown("##### 📥 示例数据")
        st.caption("快速导入 5 条演示职位")
        if st.button("导入示例数据", use_container_width=True):
            _seed_sample_jobs()
            clear_jobs_cache()
            job_recommender.refresh_index()
            st.success("✅ 示例数据已导入")
            st.rerun()

    with c3:
        st.markdown("##### ℹ️ 数据库信息")
        st.caption(f"类型: `{settings.database.backend.upper()}`")
        st.caption(f"库名: `{settings.database.mysql_database}`")
        st.caption(f"地址: `{settings.database.mysql_host}:{settings.database.mysql_port}`")

    st.markdown('</div>', unsafe_allow_html=True)

    # ---- 数据预览 ----
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    jobs = load_jobs()
    st.markdown(f"##### 📋 职位数据（共 {len(jobs)} 条）")

    if jobs:
        df = pd.DataFrame(jobs)
        display_cols = [
            c for c in ["id", "title", "company", "city", "salary_min", "salary_max",
                        "source", "experience", "education"]
            if c in df.columns
        ]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.markdown("""
        <div class="guide-card">
            <p>💡 数据库为空 — 点击上方「导入示例数据」快速体验，或启动爬虫采集真实数据。</p>
        </div>
        """, unsafe_allow_html=True)
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
    """
    AI 智能报告（简化版 / UI 增强版）。

    基于现有分析模块自动生成结构化 Markdown 报告；
    后续可接入大模型 API 增强叙述能力。
    """
    st.markdown("""
    <div class="page-hero">
        <div class="page-title">📋 AI 智能报告</div>
        <div class="page-subtitle">自动汇总平台数据与分析结果，一键生成可下载的 Markdown 分析报告</div>
    </div>
    """, unsafe_allow_html=True)

    c_btn, c_info = st.columns([1, 3])
    with c_btn:
        gen_clicked = st.button("🤖 生成报告", type="primary", use_container_width=True)
    with c_info:
        st.caption("基于当前数据库内容，自动调用各分析模块汇总生成结构化报告。")

    if gen_clicked:
        with st.spinner("正在汇总分析结果..."):
            report = _build_ai_report(jobs)

        st.markdown('<div class="report-box">', unsafe_allow_html=True)
        st.markdown(report)
        st.markdown('</div>', unsafe_allow_html=True)

        st.download_button(
            "⬇️ 下载报告 (Markdown)",
            data=report,
            file_name=f"招聘分析报告_{datetime.now():%Y%m%d_%H%M}.md",
            mime="text/markdown",
            type="primary",
        )

    # 未生成时显示占位引导
    if not gen_clicked:
        st.markdown("""
        <div class="guide-card">
            <p>💡 点击上方「生成报告」按钮，系统将自动拉取当前数据库中的所有职位数据，
            调用技能 NLP、薪资预测等分析模块，生成一份包含数据概览、技能洞察、模型指标的 Markdown 报告。</p>
        </div>
        """, unsafe_allow_html=True)


def _build_ai_report(jobs: list[dict[str, Any]]) -> str:
    """根据当前数据构建 Markdown 格式分析报告。"""
    metrics = compute_overview_metrics(jobs)
    lines = [
        f"# 招聘数据分析报告",
        f"",
        f"> 生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}  ",
        f"> 数据库: `{settings.database.backend}`  ",
        f"",
        f"## 一、数据概览",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 总职位数 | {metrics['total_jobs']} |",
        f"| 平均薪资 (K/月) | {metrics['avg_salary']} |",
        f"| 热门城市 | {metrics['top_city']} |",
        f"| 热门技能 | {metrics['top_skill']} |",
        f"",
    ]

    if jobs:
        freq = skill_analyzer.get_skills_frequency(top_n=5)
        lines.append("## 二、技能洞察")
        lines.append("")
        for skill, count in freq.most_common(5):
            lines.append(f"- **{skill}**: 出现 {count} 次")
        lines.append("")

        trending = skill_analyzer.get_trending_skills(top_n=5)
        if trending:
            lines.append("### 趋势技能")
            lines.append("")
            for item in trending:
                lines.append(
                    f"- {item['skill']}（评分 {item['score']}，近期 {item['recent_count']} 条）"
                )
            lines.append("")

        if salary_predictor.is_trained or _try_load_model():
            lines.append("## 三、薪资模型")
            lines.append("")
            if salary_predictor.metrics:
                m = salary_predictor.metrics
                lines.append(f"- R²: {m.get('r2', 0):.4f}")
                lines.append(f"- MAE: {m.get('mae', 0):.2f} K/月")
                lines.append(f"- RMSE: {m.get('rmse', 0):.2f} K/月")
            lines.append("")

    lines.extend([
        "## 四、建议与结论",
        "",
        "1. 关注高频技能组合，优化团队技术栈规划。",
        "2. 结合城市薪资分布制定有竞争力的薪酬策略。",
        "3. 定期执行数据清洗，保持分析结果准确性。",
        "4. 利用岗位推荐模块匹配候选人画像与开放职位。",
        "",
        "---",
        "*本报告由招聘数据分析平台自动生成。*",
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
