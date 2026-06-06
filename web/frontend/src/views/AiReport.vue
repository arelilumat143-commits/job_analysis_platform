<!-- ============================================================
 AiReport v2 — AI 招聘市场分析报告（结构化报告版）
 从"聊天问答"升级为"专业数据分析报告"
 数据来源：/api/analysis/market-insight + /api/jobs/stats + /api/analysis/*
 ============================================================ -->
<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import { useChart } from '../composables/useChart.js'

const store = useAppStore()
const { get } = useApi()
const { init: initChart, setOption: setChart, readCssVar } = useChart()

const loading = ref(true)
const insight = ref(null)
const stats = ref(null)
const salaryData = ref(null)
const skillData = ref(null)
const industryData = ref(null)
const experienceData = ref(null)
const educationData = ref(null)

// ---- 报告生成时间 ----
const reportTime = computed(() => {
  return new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
})

// ---- 加载所有数据 ----
async function loadData() {
  loading.value = true
  const [ins, st, sa, sk, ind, exp, edu] = await Promise.all([
    get('/api/analysis/market-insight'),
    get('/api/jobs/stats'),
    get('/api/analysis/salary'),
    get('/api/analysis/skill'),
    get('/api/analysis/industry'),
    get('/api/analysis/experience'),
    get('/api/analysis/education'),
  ])
  if (ins) insight.value = ins
  if (st) stats.value = st
  if (sa) salaryData.value = sa
  if (sk) skillData.value = sk
  if (ind) industryData.value = ind
  if (exp) experienceData.value = exp
  if (edu) educationData.value = edu
  loading.value = false
  await nextTick()
  renderCharts()
}

// ---- 市场健康度颜色 ----
const healthColor = computed(() => {
  const s = insight.value?.market_health?.score || 0
  if (s >= 80) return 'var(--green)'
  if (s >= 60) return 'var(--primary)'
  if (s >= 40) return 'var(--orange)'
  return 'var(--red)'
})

// ---- 图表渲染 ----
function renderCharts() {
  renderExpChart()
  renderEduChart()
}

function renderExpChart() {
  const c = initChart('chart-exp')
  if (!c || !experienceData.value?.length) return
  const data = experienceData.value
  setChart('chart-exp', {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 10, bottom: 60 },
    xAxis: {
      type: 'category', data: data.map(x => x.experience),
      axisLabel: { rotate: 25, fontSize: 11, color: readCssVar('--text-2') },
    },
    yAxis: {
      type: 'value', name: '职位数',
      splitLine: { lineStyle: { color: readCssVar('--border'), type: 'dashed' } },
    },
    series: [{
      type: 'bar', data: data.map(x => x.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: readCssVar('--primary') },
          { offset: 1, color: readCssVar('--primary-light') }
        ]),
        borderRadius: [6, 6, 0, 0],
      },
      barWidth: '50%',
    }],
    backgroundColor: 'transparent',
  })
}

function renderEduChart() {
  const c = initChart('chart-edu')
  if (!c || !educationData.value?.length) return
  const data = educationData.value
  const colors = [readCssVar('--primary'), readCssVar('--green'), readCssVar('--orange'), readCssVar('--purple'), readCssVar('--red')]
  setChart('chart-edu', {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['50%', '55%'],
      data: data.map((x, i) => ({ name: x.education, value: x.count, itemStyle: { color: colors[i % colors.length] } })),
      label: { color: readCssVar('--text-2'), fontSize: 12 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' } },
    }],
    backgroundColor: 'transparent',
  })
}

// ---- 技能需求等级 ----
function skillLevel(idx) {
  if (idx < 5) return 'hot'
  if (idx < 15) return 'warm'
  return 'normal'
}

import * as echarts from 'echarts'

onMounted(() => loadData())
</script>

<template>
  <div class="page">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-wrap">
      <div class="pulse-dot"></div>
      <span>正在生成分析报告...</span>
    </div>

    <template v-else>
      <!-- ====== 报告头部 ====== -->
      <div class="report-header">
        <div class="report-cover">
          <div class="cover-badge">AI 生成</div>
          <h1 class="cover-title">招聘市场数据分析报告</h1>
          <div class="cover-meta">
            <span>基于 {{ stats?.total?.toLocaleString() || '--' }} 条真实职位数据</span>
            <span class="meta-sep">|</span>
            <span>{{ reportTime }}</span>
          </div>
        </div>
      </div>

      <!-- ====== 一、执行摘要 ====== -->
      <section class="report-section">
        <h2 class="section-title"><span class="section-num">01</span> 执行摘要</h2>
        <div class="exec-summary">
          <p>{{ insight?.ai_summary || '数据加载中...' }}</p>
        </div>

        <!-- 关键指标行 -->
        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-value">{{ stats?.total?.toLocaleString() || '--' }}</div>
            <div class="kpi-label">市场职位总量</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value accent">{{ insight?.salary_overview?.avg_salary?.toFixed(1) || '--' }}K</div>
            <div class="kpi-label">市场平均月薪</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value" :style="{ color: healthColor }">{{ insight?.market_health?.score || '--' }}</div>
            <div class="kpi-label">{{ insight?.market_health?.label || '市场健康度' }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value">{{ insight?.salary_overview?.high_salary_pct || '--' }}%</div>
            <div class="kpi-label">高薪岗位占比 (30K+)</div>
          </div>
        </div>
      </section>

      <!-- ====== 二、关键发现 ====== -->
      <section class="report-section" v-if="insight?.key_findings?.length">
        <h2 class="section-title"><span class="section-num">02</span> 关键发现</h2>
        <div class="findings-grid">
          <div class="finding-card" v-for="(f, i) in insight.key_findings" :key="i">
            <span class="finding-num">{{ i + 1 }}</span>
            <span class="finding-text">{{ f }}</span>
          </div>
        </div>
      </section>

      <!-- ====== 三、市场健康度 ====== -->
      <section class="report-section" v-if="insight?.market_health">
        <h2 class="section-title"><span class="section-num">03</span> 市场健康度评估</h2>
        <div class="health-section">
          <div class="health-gauge">
            <svg viewBox="0 0 120 120" width="140" height="140">
              <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" stroke-width="10"/>
              <circle cx="60" cy="60" r="52" fill="none" :stroke="healthColor" stroke-width="10"
                stroke-linecap="round" stroke-dasharray="326.7"
                :stroke-dashoffset="326.7 - (326.7 * (insight.market_health.score || 0) / 100)"
                transform="rotate(-90 60 60)" style="transition: stroke-dashoffset 1.2s ease"/>
              <text x="60" y="56" text-anchor="middle" fill="var(--text-1)" font-size="28" font-weight="800">{{ insight.market_health.score }}</text>
              <text x="60" y="76" text-anchor="middle" fill="var(--text-3)" font-size="12">{{ insight.market_health.label }}</text>
            </svg>
          </div>
          <div class="health-factors">
            <div class="hf-item" v-for="f in insight.market_health.factors || []" :key="f">
              <span class="hf-dot" :style="{ background: healthColor }"></span>
              {{ f }}
            </div>
          </div>
        </div>
      </section>

      <!-- ====== 四、城市分析 ====== -->
      <section class="report-section" v-if="insight?.top_cities?.length">
        <h2 class="section-title"><span class="section-num">04</span> 城市分布与薪资对比</h2>
        <div class="city-table-wrap">
          <table class="city-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>城市</th>
                <th>职位数量</th>
                <th>占比</th>
                <th>平均薪资</th>
                <th>热度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in insight.top_cities.slice(0, 10)" :key="c.city">
                <td><span class="ct-rank" :class="'r' + (i + 1)">{{ i + 1 }}</span></td>
                <td class="ct-name">{{ c.city }}</td>
                <td>{{ c.count.toLocaleString() }}</td>
                <td>{{ stats ? (c.count / stats.total * 100).toFixed(1) : '--' }}%</td>
                <td class="ct-salary">{{ c.avg_salary || '--' }}K</td>
                <td>
                  <div class="ct-bar-bg">
                    <div class="ct-bar" :style="{ width: stats ? (c.count / (insight.top_cities[0]?.count || 1) * 100) + '%' : '0%' }"></div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ====== 五、薪资分析 ====== -->
      <section class="report-section" v-if="salaryData">
        <h2 class="section-title"><span class="section-num">05</span> 薪资结构分析</h2>
        <div class="salary-stats">
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.mean?.toFixed(1) }}K</div>
            <div class="ss-lbl">平均值</div>
          </div>
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.median?.toFixed(1) }}K</div>
            <div class="ss-lbl">中位数</div>
          </div>
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.q25?.toFixed(1) }}K</div>
            <div class="ss-lbl">25%分位</div>
          </div>
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.q75?.toFixed(1) }}K</div>
            <div class="ss-lbl">75%分位</div>
          </div>
          <div class="ss-item">
            <div class="ss-val">{{ salaryData.basic_stats?.count?.toLocaleString() || '--' }}</div>
            <div class="ss-lbl">样本量</div>
          </div>
        </div>
      </section>

      <!-- ====== 六、技能需求 ====== -->
      <section class="report-section" v-if="skillData?.top_skills?.length">
        <h2 class="section-title"><span class="section-num">06</span> 热门技能需求</h2>
        <div class="skills-cloud">
          <span class="sc-item" v-for="(s, i) in skillData.top_skills.slice(0, 24)" :key="s.skill"
            :class="'sc-' + skillLevel(i)">
            {{ s.skill }}
            <small>{{ s.count }}</small>
          </span>
        </div>
        <div class="sc-empty" v-if="!skillData.top_skills.length">
          技能数据尚未采集，请先运行详情页爬虫填充技能字段。
        </div>
      </section>

      <!-- ====== 七、经验与学历 ====== -->
      <section class="report-section">
        <h2 class="section-title"><span class="section-num">07</span> 经验与学历要求</h2>
        <div class="chart-row">
          <div class="chart-half">
            <h4 class="chart-subtitle">经验要求分布</h4>
            <div id="chart-exp" style="width:100%;height:280px"></div>
            <div class="chart-empty" v-if="!experienceData?.length">暂无经验要求数据</div>
          </div>
          <div class="chart-half">
            <h4 class="chart-subtitle">学历要求分布</h4>
            <div id="chart-edu" style="width:100%;height:280px"></div>
            <div class="chart-empty" v-if="!educationData?.length">暂无学历要求数据</div>
          </div>
        </div>
      </section>

      <!-- ====== 八、行业概览 ====== -->
      <section class="report-section" v-if="industryData?.length">
        <h2 class="section-title"><span class="section-num">08</span> 行业分布</h2>
        <div class="industry-list">
          <div class="ind-item" v-for="ind in industryData.slice(0, 10)" :key="ind.industry">
            <span class="ind-name">{{ ind.industry }}</span>
            <span class="ind-count">{{ ind.count?.toLocaleString() || '--' }} 条</span>
          </div>
        </div>
      </section>

      <!-- ====== 九、建议与展望 ====== -->
      <section class="report-section">
        <h2 class="section-title"><span class="section-num">09</span> 建议与展望</h2>
        <div class="recommendations">
          <div class="rec-item">
            <div class="rec-icon">数据</div>
            <div class="rec-content">
              <div class="rec-title">扩充数据来源</div>
              <div class="rec-desc">当前数据以智联招聘为主，建议增加 BOSS直聘、拉勾网等渠道，提升数据多样性和代表性。</div>
            </div>
          </div>
          <div class="rec-item">
            <div class="rec-icon">技能</div>
            <div class="rec-content">
              <div class="rec-title">完善技能标签</div>
              <div class="rec-desc">运行详情页爬虫补充技能、行业、经验等字段，当前大量职位缺少结构化标签。</div>
            </div>
          </div>
          <div class="rec-item">
            <div class="rec-icon">AI</div>
            <div class="rec-content">
              <div class="rec-title">接入 AI 大模型</div>
              <div class="rec-desc">当前使用本地规则引擎生成报告，接入 DeepSeek API 可实现更深入的个性化分析。</div>
            </div>
          </div>
          <div class="rec-item">
            <div class="rec-icon">趋势</div>
            <div class="rec-content">
              <div class="rec-title">增加时间维度</div>
              <div class="rec-desc">定期采集数据，建立时间序列分析能力，追踪市场薪资和技能需求变化趋势。</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 报告脚注 -->
      <div class="report-footer">
        <p>本报告由 AI 自动生成，数据来源为招聘平台公开职位信息。仅供学习参考，不构成职业建议。</p>
        <p>报告生成时间：{{ reportTime }} | 招聘数据分析平台</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ===== 加载 ===== */
.loading-wrap {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 0; color: var(--text-3);
}
.pulse-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: var(--primary); animation: pulse 1.2s infinite;
}
@keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1.2)} }

/* ===== 报告头部 ===== */
.report-header {
  background: linear-gradient(135deg, var(--primary-soft), var(--bg-card));
  border-radius: var(--radius); padding: 40px 36px; margin-bottom: 28px;
  text-align: center; box-shadow: var(--shadow);
}
.cover-badge {
  display: inline-block; padding: 4px 16px; border-radius: 16px;
  background: var(--primary); color: var(--text-inverse);
  font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; margin-bottom: 16px;
}
.cover-title {
  font-size: 28px; font-weight: 800; color: var(--text-1);
  margin: 0 0 12px; letter-spacing: 0.02em;
}
.cover-meta { font-size: 14px; color: var(--text-3); }
.meta-sep { margin: 0 10px; color: var(--border); }

/* ===== 报告区块 ===== */
.report-section { margin-bottom: 32px; }
.section-title {
  font-size: 20px; font-weight: 700; color: var(--text-1);
  margin: 0 0 18px; padding-bottom: 12px;
  border-bottom: 2px solid var(--border); display: flex; align-items: center; gap: 12px;
}
.section-num {
  font-size: 14px; font-weight: 700; color: var(--primary);
  background: var(--primary-soft); padding: 4px 10px; border-radius: 6px;
}

/* 执行摘要 */
.exec-summary {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px 24px; margin-bottom: 20px;
  border-left: 4px solid var(--primary); box-shadow: var(--shadow);
}
.exec-summary p {
  font-size: 15px; line-height: 1.9; color: var(--text-2); margin: 0;
}

/* KPI 行 */
.kpi-row {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
}
.kpi-card {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px; text-align: center; box-shadow: var(--shadow);
}
.kpi-value {
  font-size: 28px; font-weight: 800; color: var(--text-1); margin-bottom: 4px;
}
.kpi-value.accent { color: var(--primary); }
.kpi-label { font-size: 12px; color: var(--text-3); }

/* 关键发现 */
.findings-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;
}
.finding-card {
  display: flex; align-items: flex-start; gap: 12px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 16px 20px; box-shadow: var(--shadow);
  border: 1px solid var(--border); transition: all 0.2s;
}
.finding-card:hover { border-color: var(--primary-light); transform: translateY(-1px); }
.finding-num {
  width: 28px; height: 28px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: var(--primary-soft); color: var(--primary);
  font-size: 14px; font-weight: 700; flex-shrink: 0;
}
.finding-text { font-size: 14px; color: var(--text-2); line-height: 1.7; }

/* 市场健康度 */
.health-section {
  display: flex; align-items: center; gap: 40px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 28px 32px; box-shadow: var(--shadow);
}
.health-gauge { flex-shrink: 0; }
.health-factors { display: flex; flex-direction: column; gap: 8px; }
.hf-item {
  font-size: 13px; color: var(--text-2); display: flex; align-items: center; gap: 10px;
}
.hf-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

/* 城市表格 */
.city-table-wrap { background: var(--bg-card); border-radius: var(--radius-sm); box-shadow: var(--shadow); overflow: hidden; }
.city-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.city-table th {
  text-align: left; padding: 12px 16px; background: var(--bg-sidebar);
  color: var(--text-2); font-weight: 500; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.city-table td { padding: 12px 16px; border-top: 1px solid var(--border); color: var(--text-1); }
.ct-rank {
  width: 26px; height: 26px; border-radius: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; background: var(--bg-page); color: var(--text-3);
}
.ct-rank.r1 { background: var(--primary-soft); color: var(--primary); }
.ct-rank.r2 { background: var(--green-soft); color: var(--green); }
.ct-rank.r3 { background: var(--orange); color: var(--text-inverse); opacity: 0.7; }
.ct-name { font-weight: 500; }
.ct-salary { color: var(--primary); font-weight: 600; }
.ct-bar-bg { width: 100%; height: 8px; border-radius: 4px; background: var(--bg-page); }
.ct-bar { height: 100%; border-radius: 4px; background: var(--primary); transition: width 0.6s ease; }

/* 薪资统计 */
.salary-stats {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;
}
.ss-item {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px; text-align: center; box-shadow: var(--shadow);
}
.ss-val { font-size: 22px; font-weight: 700; color: var(--primary); }
.ss-lbl { font-size: 11px; color: var(--text-3); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.04em; }

/* 技能云 */
.skills-cloud {
  display: flex; flex-wrap: wrap; gap: 10px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px 24px; box-shadow: var(--shadow);
}
.sc-item {
  padding: 6px 14px; border-radius: 8px; font-size: 14px; font-weight: 500;
  display: inline-flex; align-items: center; gap: 6px;
}
.sc-item small { font-size: 11px; opacity: 0.7; }
.sc-hot { background: var(--red-soft); color: var(--red); font-size: 16px; }
.sc-warm { background: var(--primary-soft); color: var(--primary); }
.sc-normal { background: var(--bg-page); color: var(--text-3); }
.sc-empty { color: var(--text-3); font-size: 13px; padding: 16px; }

/* 图表行 */
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.chart-half {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px 24px; box-shadow: var(--shadow);
}
.chart-subtitle { font-size: 14px; font-weight: 600; color: var(--text-1); margin: 0 0 8px; }
.chart-empty { color: var(--text-3); font-size: 13px; padding: 20px; text-align: center; }

/* 行业列表 */
.industry-list {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 16px 20px; box-shadow: var(--shadow);
  display: flex; flex-wrap: wrap; gap: 8px;
}
.ind-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px; border-radius: 8px; background: var(--bg-page);
}
.ind-name { font-size: 13px; color: var(--text-1); font-weight: 500; }
.ind-count { font-size: 12px; color: var(--text-3); }

/* 建议 */
.recommendations {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px;
}
.rec-item {
  display: flex; gap: 14px; background: var(--bg-card);
  border-radius: var(--radius-sm); padding: 20px; box-shadow: var(--shadow);
  border: 1px solid var(--border); transition: all 0.2s;
}
.rec-item:hover { border-color: var(--primary-light); }
.rec-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  background: var(--primary-soft); color: var(--primary);
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.rec-title { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.rec-desc { font-size: 12px; color: var(--text-3); line-height: 1.6; }

/* 脚注 */
.report-footer {
  margin-top: 40px; padding-top: 24px;
  border-top: 2px solid var(--border); text-align: center;
}
.report-footer p {
  font-size: 12px; color: var(--text-3); margin: 0 0 4px;
}

@media (max-width: 768px) {
  .cover-title { font-size: 22px; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .findings-grid, .chart-row, .recommendations { grid-template-columns: 1fr; }
  .health-section { flex-direction: column; }
  .salary-stats { grid-template-columns: repeat(3, 1fr); }
}
</style>
