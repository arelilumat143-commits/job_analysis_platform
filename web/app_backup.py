"""
招聘数据分析平台 — Streamlit 主入口。

多页面应用，集成数据清洗、技能 NLP、薪资预测与岗位推荐等分析能力。
运行方式（在项目根目录）::

    streamlit run web/app.py
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

# ---------------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="招聘数据分析平台",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 导航页面列表
_NAV_PAGES: list[str] = [
    "首页概览",
    "薪资分析",
    "技能分析",
    "岗位推荐",
    "数据管理",
    "AI智能报告",
]


# ---------------------------------------------------------------------------
# 数据加载（缓存）
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 侧边栏
# ---------------------------------------------------------------------------


def render_sidebar() -> str:
    """
    渲染左侧导航栏。

    Returns:
        当前选中的页面名称。
    """
    st.sidebar.title("📊 招聘分析平台")
    st.sidebar.caption(f"数据库: {settings.database.backend}")
    if settings.debug:
        st.sidebar.warning("调试模式已开启")

    page = st.sidebar.radio(
        "功能导航",
        _NAV_PAGES,
        label_visibility="collapsed",
    )

    st.sidebar.divider()
    st.sidebar.markdown("**系统信息**")
    st.sidebar.text(f"项目路径:\n{BASE_DIR}")
    st.sidebar.text(f"DB: {settings.database.sqlite_path.name}")

    if st.sidebar.button("🔄 刷新数据缓存"):
        clear_jobs_cache()
        job_recommender.refresh_index()
        st.sidebar.success("缓存已刷新")
        st.rerun()

    return page


# ---------------------------------------------------------------------------
# 页面：首页概览
# ---------------------------------------------------------------------------


def page_overview(jobs: list[dict[str, Any]]) -> None:
    """首页概览：关键指标卡片与基础图表。"""
    st.header("首页概览")
    st.markdown("平台数据总览与核心指标一览。")

    metrics = compute_overview_metrics(jobs)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总职位数", metrics["total_jobs"])
    col2.metric("平均薪资 (K/月)", metrics["avg_salary"])
    col3.metric("热门城市", metrics["top_city"])
    col4.metric("热门技能", metrics["top_skill"])

    if not jobs:
        st.info("暂无职位数据，请前往「数据管理」导入或生成示例数据。")
        return

    st.subheader("数据分布")

    c1, c2 = st.columns(2)

    with c1:
        # 城市分布
        city_counts = Counter(
            str(j.get("city") or "未知").replace("市", "") for j in jobs
        )
        df_city = pd.DataFrame(
            city_counts.most_common(10), columns=["城市", "职位数"]
        )
        fig_city = px.bar(
            df_city,
            x="城市",
            y="职位数",
            title="城市职位分布 Top 10",
            color="职位数",
            color_continuous_scale="Blues",
        )
        fig_city.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig_city, use_container_width=True)

    with c2:
        # 薪资分布
        salary_data = [
            {"薪资中位数": mid}
            for j in jobs
            if (mid := _salary_mid(j)) is not None
        ]
        if salary_data:
            df_salary = pd.DataFrame(salary_data)
            fig_sal = px.histogram(
                df_salary,
                x="薪资中位数",
                nbins=20,
                title="薪资分布 (K/月)",
                color_discrete_sequence=["#636EFA"],
            )
            fig_sal.update_layout(height=380)
            st.plotly_chart(fig_sal, use_container_width=True)
        else:
            st.warning("暂无有效薪资数据。")

    # 来源分布饼图
    source_counts = Counter(j.get("source") or "未知" for j in jobs)
    df_source = pd.DataFrame(
        list(source_counts.items()), columns=["来源", "数量"]
    )
    fig_pie = px.pie(df_source, names="来源", values="数量", title="招聘来源占比")
    fig_pie.update_layout(height=360)
    st.plotly_chart(fig_pie, use_container_width=True)


# ---------------------------------------------------------------------------
# 页面：薪资分析
# ---------------------------------------------------------------------------


def page_salary(jobs: list[dict[str, Any]]) -> None:
    """薪资分析：分布可视化、模型训练与单条预测。"""
    st.header("薪资分析")
    st.markdown("基于历史数据训练随机森林模型，预测职位薪资区间。")

    if len(jobs) < 10:
        st.warning("有效职位不足 10 条，请先在「数据管理」补充数据后再训练模型。")

    tab1, tab2, tab3 = st.tabs(["薪资分布", "模型训练", "薪资预测"])

    with tab1:
        records = []
        for job in jobs:
            mid = _salary_mid(job)
            if mid is None:
                continue
            records.append(
                {
                    "城市": str(job.get("city") or "未知"),
                    "行业": str(job.get("industry") or "未知"),
                    "薪资中位数": mid,
                }
            )
        if records:
            df = pd.DataFrame(records)
            fig = px.box(
                df,
                x="城市",
                y="薪资中位数",
                color="城市",
                title="各城市薪资箱线图 (K/月)",
            )
            fig.update_layout(height=420, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无薪资数据。")

    with tab2:
        st.subheader("训练随机森林模型")
        if st.button("开始训练", type="primary"):
            try:
                with st.spinner("训练中..."):
                    metrics = salary_predictor.train(model_type="random_forest")
                st.success("模型训练完成并已保存。")
                m1, m2, m3 = st.columns(3)
                m1.metric("R²", f"{metrics['r2']:.4f}")
                m2.metric("MAE (K)", f"{metrics['mae']:.2f}")
                m3.metric("RMSE (K)", f"{metrics['rmse']:.2f}")

                if salary_predictor.is_trained:
                    importance = salary_predictor.get_feature_importance(top_n=10)
                    df_imp = pd.DataFrame(importance)
                    fig_imp = px.bar(
                        df_imp,
                        x="importance",
                        y="feature",
                        orientation="h",
                        title="特征重要性 Top 10",
                    )
                    fig_imp.update_layout(height=400)
                    st.plotly_chart(fig_imp, use_container_width=True)
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"训练失败: {exc}")

        if salary_predictor.is_trained and salary_predictor.metrics:
            st.caption(f"当前模型指标: {salary_predictor.metrics}")

    with tab3:
        st.subheader("薪资预测")
        if not salary_predictor.is_trained:
            try:
                salary_predictor.load_model()
            except FileNotFoundError:
                st.info("请先训练模型或确保模型文件存在。")

        with st.form("salary_predict_form"):
            c1, c2 = st.columns(2)
            city = c1.text_input("城市", value="北京")
            industry = c2.text_input("行业", value="互联网")
            experience = c1.selectbox(
                "经验",
                ["不限", "应届生", "1-3年", "3-5年", "5-10年", "10年以上"],
            )
            education = c2.selectbox(
                "学历",
                ["不限", "大专", "本科", "硕士", "博士"],
            )
            skills_text = st.text_input(
                "技能（逗号分隔）",
                value="Python, MySQL, Django",
            )
            submitted = st.form_submit_button("预测薪资", type="primary")

        if submitted and salary_predictor.is_trained:
            skills = [s.strip() for s in skills_text.split(",") if s.strip()]
            result = salary_predictor.predict(
                {
                    "city": city,
                    "industry": industry,
                    "experience": experience,
                    "education": education,
                    "skills": skills,
                }
            )
            st.metric("预测薪资中位数", f"{result['salary_mid']} K/月")
            st.write(
                f"参考区间: **{result['salary_min']} ~ {result['salary_max']}** {result['unit']}"
            )


# ---------------------------------------------------------------------------
# 页面：技能分析
# ---------------------------------------------------------------------------


def page_skills(jobs: list[dict[str, Any]]) -> None:
    """技能分析：频率、共现、关联规则与趋势。"""
    st.header("技能分析")
    st.markdown("基于 jieba + TF-IDF 的技能挖掘与关联分析。")

    if not jobs:
        st.info("暂无数据。")
        return

    tab1, tab2, tab3 = st.tabs(["技能频率", "共现分析", "趋势与关联"])

    with tab1:
        freq = skill_analyzer.get_skills_frequency(top_n=20)
        if not freq:
            st.warning("未能提取技能关键词。")
        else:
            df = pd.DataFrame(freq.most_common(), columns=["技能", "频次"])
            fig = px.bar(
                df,
                x="频次",
                y="技能",
                orientation="h",
                title="技能出现频率 Top 20",
                color="频次",
                color_continuous_scale="Viridis",
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        co = skill_analyzer.get_skill_cooccurrence(top_n=15)
        if not co:
            st.warning("共现数据不足。")
        else:
            rows = [
                {"技能A": pair[0], "技能B": pair[1], "共现次数": count}
                for pair, count in co.most_common()
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab3:
        trending = skill_analyzer.get_trending_skills(top_n=10)
        if trending:
            df_trend = pd.DataFrame(trending)
            fig_t = px.bar(
                df_trend,
                x="skill",
                y="score",
                title="趋势技能综合评分",
                color="score",
                color_continuous_scale="Oranges",
            )
            st.plotly_chart(fig_t, use_container_width=True)

        rules = skill_analyzer.analyze_skill_associations(
            min_support=0.01,
            top_n=10,
        )
        if rules:
            st.subheader("技能关联规则 Top 10")
            st.dataframe(pd.DataFrame(rules), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# 页面：岗位推荐
# ---------------------------------------------------------------------------


def page_recommend(jobs: list[dict[str, Any]]) -> None:
    """岗位推荐：基于职位或用户画像的相似推荐。"""
    st.header("岗位推荐")
    st.markdown("TF-IDF + 技能向量余弦相似度推荐。")

    if not jobs:
        st.info("暂无职位数据。")
        return

    job_recommender.refresh_index()

    mode = st.radio("推荐模式", ["基于职位", "基于用户画像"], horizontal=True)

    if mode == "基于职位":
        job_options = {
            f"[{j.get('id')}] {j.get('title')} - {j.get('company')}": j.get("id")
            for j in jobs
            if j.get("id") is not None
        }
        if not job_options:
            st.warning("无有效职位 ID。")
            return

        selected = st.selectbox("选择参考职位", list(job_options.keys()))
        top_n = st.slider("推荐数量", 3, 20, 10)
        sort_by = st.selectbox(
            "排序方式",
            ["composite", "similarity", "salary", "city"],
            format_func=lambda x: {
                "composite": "综合得分",
                "similarity": "相似度",
                "salary": "薪资",
                "city": "城市匹配",
            }[x],
        )

        if st.button("获取推荐", type="primary"):
            job_id = job_options[selected]
            results = job_recommender.recommend_for_job(
                int(job_id),
                top_n=top_n,
                sort_by=sort_by,  # type: ignore[arg-type]
            )
            _render_recommend_results(results)

    else:
        with st.form("profile_form"):
            skills_text = st.text_input("技能", "Python, Django, MySQL")
            city = st.text_input("期望城市", "北京")
            min_sal = st.number_input("期望最低薪资 (K)", 10.0, 100.0, 20.0)
            max_sal = st.number_input("期望最高薪资 (K)", 10.0, 100.0, 35.0)
            title = st.text_input("意向岗位", "Python 开发工程师")
            top_n = st.slider("推荐数量", 3, 20, 10)
            submitted = st.form_submit_button("推荐岗位", type="primary")

        if submitted:
            skills = [s.strip() for s in skills_text.split(",") if s.strip()]
            results = job_recommender.recommend_for_profile(
                {
                    "skills": skills,
                    "city": city,
                    "preferred_city": city,
                    "min_salary": min_sal,
                    "max_salary": max_sal,
                    "title": title,
                },
                top_n=top_n,
            )
            _render_recommend_results(results)


def _render_recommend_results(results: list[dict[str, Any]]) -> None:
    """渲染推荐结果列表。"""
    if not results:
        st.warning("未找到匹配的推荐岗位。")
        return

    rows = []
    for item in results:
        job = item["job"]
        rows.append(
            {
                "职位": job.get("title"),
                "公司": job.get("company"),
                "城市": job.get("city"),
                "相似度": item["similarity"],
                "综合得分": item["composite_score"],
                "薪资中位数": item.get("salary_mid"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# 页面：数据管理
# ---------------------------------------------------------------------------


def page_data_management() -> None:
    """数据管理：查看、清洗与示例数据导入。"""
    st.header("数据管理")
    st.markdown("职位数据的查看、清洗与维护。")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🧹 执行数据清洗", type="primary"):
            try:
                with st.spinner("清洗中..."):
                    stats = data_cleaner.clean_all()
                clear_jobs_cache()
                job_recommender.refresh_index()
                st.success(
                    f"清洗完成：处理 {stats['processed']} 条，"
                    f"新增 {stats['added']}，更新 {stats['updated']}"
                )
            except Exception as exc:
                st.error(f"清洗失败: {exc}")

    with col2:
        if st.button("📥 导入示例数据"):
            _seed_sample_jobs()
            clear_jobs_cache()
            job_recommender.refresh_index()
            st.success("示例数据已导入。")
            st.rerun()

    with col3:
        st.caption(f"数据库: `{settings.database.url}`")

    jobs = load_jobs()
    st.metric("当前职位总数", len(jobs))

    if jobs:
        df = pd.DataFrame(jobs)
        display_cols = [
            c
            for c in [
                "id",
                "title",
                "company",
                "city",
                "salary_min",
                "salary_max",
                "source",
                "experience",
                "education",
            ]
            if c in df.columns
        ]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("数据库为空，可点击「导入示例数据」快速体验。")


def _seed_sample_jobs() -> None:
    """写入一批示例职位数据。"""
    samples = [
        {
            "title": "Python 后端工程师",
            "company": "星云科技",
            "city": "北京",
            "industry": "互联网",
            "source": "boss",
            "experience": "3-5年",
            "education": "本科",
            "skills": ["Python", "Django", "MySQL", "Redis"],
            "salary_min": 25,
            "salary_max": 40,
            "description": "负责后端 API 开发，熟悉 Python 与 Django。",
            "url": "https://example.com/jobs/101",
        },
        {
            "title": "Python 数据分析师",
            "company": "数澜信息",
            "city": "上海",
            "industry": "金融",
            "source": "lagou",
            "experience": "1-3年",
            "education": "硕士",
            "skills": ["Python", "Pandas", "机器学习", "SQL"],
            "salary_min": 20,
            "salary_max": 35,
            "description": "数据分析与机器学习建模。",
            "url": "https://example.com/jobs/102",
        },
        {
            "title": "Java 开发工程师",
            "company": "云帆软件",
            "city": "深圳",
            "industry": "互联网",
            "source": "boss",
            "experience": "3-5年",
            "education": "本科",
            "skills": ["Java", "Spring Boot", "MySQL"],
            "salary_min": 22,
            "salary_max": 38,
            "description": "Java 微服务开发。",
            "url": "https://example.com/jobs/103",
        },
        {
            "title": "前端开发工程师",
            "company": "前端工场",
            "city": "杭州",
            "industry": "电商",
            "source": "boss",
            "experience": "1-3年",
            "education": "本科",
            "skills": ["Vue", "JavaScript", "TypeScript"],
            "salary_min": 18,
            "salary_max": 30,
            "description": "Vue 前端开发。",
            "url": "https://example.com/jobs/104",
        },
        {
            "title": "算法工程师",
            "company": "智算科技",
            "city": "北京",
            "industry": "人工智能",
            "source": "lagou",
            "experience": "3-5年",
            "education": "硕士",
            "skills": ["Python", "PyTorch", "深度学习", "NLP"],
            "salary_min": 35,
            "salary_max": 60,
            "description": "大模型与 NLP 算法研发。",
            "url": "https://example.com/jobs/105",
        },
    ]
    for job in samples:
        db_manager.add_job(job)


# ---------------------------------------------------------------------------
# 页面：AI 智能报告
# ---------------------------------------------------------------------------


def page_ai_report(jobs: list[dict[str, Any]]) -> None:
    """
    AI 智能报告（简化版）。

    基于现有分析模块自动生成结构化 Markdown 报告；
    后续可接入大模型 API 增强叙述能力。
    """
    st.header("AI 智能报告")
    st.markdown("自动汇总平台数据与分析结果，生成可读性报告。")

    if st.button("生成报告", type="primary"):
        with st.spinner("正在汇总分析结果..."):
            report = _build_ai_report(jobs)
        st.markdown(report)

        st.download_button(
            "下载报告 (Markdown)",
            data=report,
            file_name=f"招聘分析报告_{datetime.now():%Y%m%d_%H%M}.md",
            mime="text/markdown",
        )


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

    lines.extend(
        [
            "## 四、建议与结论",
            "",
            "1. 关注高频技能组合，优化团队技术栈规划。",
            "2. 结合城市薪资分布制定有竞争力的薪酬策略。",
            "3. 定期执行数据清洗，保持分析结果准确性。",
            "4. 利用岗位推荐模块匹配候选人画像与开放职位。",
            "",
            "---",
            "*本报告由招聘数据分析平台自动生成（简化版）。*",
        ]
    )
    return "\n".join(lines)


def _try_load_model() -> bool:
    """尝试加载已保存的薪资模型。"""
    try:
        salary_predictor.load_model()
        return True
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main() -> None:
    """应用主入口：侧边栏导航 + 页面路由。"""
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
