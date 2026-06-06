<!-- ============================================================
 Overview v3 — AI 招聘市场洞察首页
 「展示价值，而非展示数据」
 功能：AI 市场摘要 / 关键发现 / 热榜 / 市场健康度 / 精选图表
 数据来源：/api/analysis/market-insight + /api/jobs/stats + /api/analysis/salary
 ============================================================ -->
<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import { useChart } from '../composables/useChart.js'
import MetricCard from '../components/MetricCard.vue'
import ChartCard from '../components/ChartCard.vue'
import * as echarts from 'echarts'

const store = useAppStore()
const { get } = useApi()
const { init: initChart, setOption: setChart, readCssVar } = useChart()

const loading = ref(true)
const insight = ref(null)
const stats = ref(null)
const salaryData = ref(null)

// ---- 加载所有数据（并发）----
async function loadData() {
  loading.value = true
  const [ins, st, sa] = await Promise.all([
    get('/api/analysis/market-insight'),
    get('/api/jobs/stats'),
    get('/api/analysis/salary'),
  ])
  if (ins) insight.value = ins
  if (st) {
    stats.value = st
    store.statsCache = st
    store.statsCacheTime = Date.now()
  }
  if (sa) salaryData.value = sa
  loading.value = false
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
function renderCityChart() {
  const c = initChart('chart-city')
  if (!c || !insight.value?.top_cities) return
  const cities = insight.value.top_cities.slice(0, 8)
  setChart('chart-city', {
    tooltip: {
      trigger: 'axis',
      formatter: (p) => {
        const d = p[0]
        const city = cities.find(x => x.city === d.name)
        return d.name + '<br/>职位数: ' + d.value.toLocaleString() + '<br/>均薪: ' + (city?.avg_salary || '--') + 'K/月'
      }
    },
    grid: { left: 55, right: 30, top: 10, bottom: 50 },
    xAxis: {
      type: 'category', data: cities.map(x => x.city),
      axisLabel: { rotate: 30, color: readCssVar('--text-2'), fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', name: '职位数',
      splitLine: { lineStyle: { color: readCssVar('--border'), type: 'dashed' } },
    },
    series: [{
      type: 'bar', data: cities.map(x => x.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: readCssVar('--primary') },
          { offset: 1, color: readCssVar('--primary-light') }
        ]),
        borderRadius: [8, 8, 0, 0],
      },
      barWidth: '55%',
      emphasis: { itemStyle: { color: readCssVar('--primary') } },
    }],
    backgroundColor: 'transparent',
  })
}

function renderSalaryChart() {
  const c = initChart('chart-salary')
  if (!c || !salaryData.value?.distribution) return
  const dist = salaryData.value.distribution
  setChart('chart-salary', {
    tooltip: {
      trigger: 'axis',
      formatter: (p) => p[0].name + '<br/>职位数: ' + p[0].value.toLocaleString()
    },
    grid: { left: 55, right: 30, top: 10, bottom: 45 },
    xAxis: {
      type: 'category', data: dist.map(x => x.range),
      axisLabel: { rotate: 30, fontSize: 10, color: readCssVar('--text-2') },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', name: '职位数',
      splitLine: { lineStyle: { color: readCssVar('--border'), type: 'dashed' } },
    },
    series: [{
      type: 'bar', data: dist.map(x => x.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: readCssVar('--green') },
          { offset: 1, color: readCssVar('--green-light') }
        ]),
        borderRadius: [8, 8, 0, 0],
      },
      barWidth: '60%',
    }],
    backgroundColor: 'transparent',
  })
}

function renderAllCharts() {
  renderCityChart()
  renderSalaryChart()
}

onMounted(async () => {
  await loadData()
  await nextTick()
  renderAllCharts()
})

watch(() => store.isDark, () => renderAllCharts())
</script>

<template>
  <div class="page">
    <!-- AI 市场摘要 -->
    <div class="market-briefing" v-if="!loading && insight">
      <div class="briefing-header">
        <div class="briefing-icon">✦</div>
        <div class="briefing-title">AI 市场洞察</div>
        <div class="briefing-badge">实时</div>
      </div>
      <p class="briefing-text">{{ insight.ai_summary }}</p>
    </div>

    <!-- 加载骨架 -->
    <div class="market-briefing skeleton" v-if="loading">
      <div class="sk-line sk-w90"></div>
      <div class="sk-line sk-w70"></div>
    </div>

    <!-- 关键指标行 -->
    <div class="metrics-grid">
      <MetricCard icon="◉" :value="stats?.total || 0" label="市场职位总量" :loading="loading" />
      <MetricCard icon="◆"
        :value="insight?.salary_overview?.avg_salary?.toFixed(1) + 'K' || '--'"
        label="市场平均月薪" :loading="loading" />
      <MetricCard icon="⬡"
        :value="insight?.market_health?.score || 0"
        :label="insight?.market_health?.label || '--'"
        :loading="loading" />
      <MetricCard icon="▲"
        :value="insight?.salary_overview?.high_salary_pct + '%' || '--'"
        label="高薪岗位占比 (30K+)" :loading="loading" />
    </div>

    <!-- 洞察双栏 -->
    <div class="insight-grid" v-if="!loading">
      <div class="insight-card findings-card">
        <div class="ic-title">💡 关键发现</div>
        <div class="finding-list">
          <div class="finding-item" v-for="(f, i) in insight?.key_findings || []" :key="i">{{ f }}</div>
        </div>
      </div>
      <div class="insight-card health-card">
        <div class="ic-title">🏥 市场健康度</div>
        <div class="health-score-wrap">
          <div class="health-ring">
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border)" stroke-width="8"/>
              <circle cx="50" cy="50" r="42" fill="none" :stroke="healthColor" stroke-width="8"
                stroke-linecap="round" stroke-dasharray="264"
                :stroke-dashoffset="264 - (264 * (insight?.market_health?.score || 0) / 100)"
                transform="rotate(-90 50 50)" style="transition: stroke-dashoffset 1s ease"/>
            </svg>
            <div class="health-num" :style="{ color: healthColor }">{{ insight?.market_health?.score || 0 }}</div>
          </div>
        </div>
        <div class="health-factors">
          <div class="hf-item" v-for="f in insight?.market_health?.factors || []" :key="f">
            <span class="hf-dot" :style="{ background: healthColor }"></span>
            {{ f }}
          </div>
        </div>
      </div>
    </div>

    <!-- 热榜双栏 -->
    <div class="double-panel" v-if="!loading">
      <div class="panel-card">
        <div class="pc-title">🔥 热门岗位 TOP8</div>
        <div class="rank-list">
          <div class="rank-item" v-for="(j, i) in insight?.top_jobs || []" :key="j.title">
            <span class="rank-num" :class="'r' + (i + 1)">{{ i + 1 }}</span>
            <span class="rank-name" :title="j.title">{{ j.title.length > 20 ? j.title.slice(0, 20) + '...' : j.title }}</span>
            <span class="rank-val">{{ j.count.toLocaleString() }} 个</span>
          </div>
        </div>
      </div>
      <div class="panel-card">
        <div class="pc-title">🏙️ 热门城市 TOP8</div>
        <div class="rank-list">
          <div class="rank-item" v-for="(c, i) in insight?.top_cities || []" :key="c.city">
            <span class="rank-num" :class="'r' + (i + 1)">{{ i + 1 }}</span>
            <span class="rank-name">{{ c.city }}</span>
            <span class="rank-sub">{{ c.count.toLocaleString() }} 职位</span>
            <span class="rank-val" style="color:var(--orange)">{{ c.avg_salary }}K</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 精选图表 -->
    <div class="chart-grid" v-if="!loading">
      <ChartCard title="各城市职位分布">
        <div id="chart-city" style="width:100%;height:300px"></div>
      </ChartCard>
      <ChartCard title="薪资区间分布">
        <div id="chart-salary" style="width:100%;height:300px"></div>
      </ChartCard>
    </div>
  </div>
</template>

<style scoped>
.market-briefing {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 24px 28px;
  margin-bottom: 20px;
  box-shadow: var(--shadow);
  border-left: 4px solid var(--primary);
}
.briefing-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
}
.briefing-icon { font-size: 20px; color: var(--primary); }
.briefing-title { font-size: 16px; font-weight: 700; color: var(--text-1); }
.briefing-badge {
  font-size: 10px; padding: 2px 10px; border-radius: 10px;
  background: var(--green-soft); color: var(--green); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.05em;
}
.briefing-text {
  font-size: 14px; line-height: 1.9; color: var(--text-2);
}

/* 骨架屏 */
.market-briefing.skeleton {
  border-left: 4px solid var(--border); padding: 24px 28px;
}
.sk-line {
  height: 16px; border-radius: 8px; margin-bottom: 10px;
  background: linear-gradient(90deg, var(--skeleton-base) 25%, var(--skeleton-shine) 50%, var(--skeleton-base) 75%);
  background-size: 200% 100%; animation: shimmer 1.5s infinite;
}
.sk-w90 { width: 90%; }
.sk-w70 { width: 70%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 洞察双栏 */
.insight-grid {
  display: grid; grid-template-columns: 1.5fr 1fr; gap: 16px; margin-bottom: 20px;
}
.insight-card {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 22px 24px; box-shadow: var(--shadow);
}
.ic-title { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 14px; }

.finding-list { display: flex; flex-direction: column; gap: 8px; }
.finding-item {
  padding: 8px 14px; border-radius: 8px;
  background: var(--bg-page); font-size: 13px; color: var(--text-2);
  line-height: 1.6; border: 1px solid var(--border);
  transition: all 0.15s;
}
.finding-item:hover { border-color: var(--primary-light); background: var(--primary-soft); }

/* 健康度环形图 */
.health-score-wrap {
  display: flex; justify-content: center; margin-bottom: 14px;
}
.health-ring {
  width: 130px; height: 130px; position: relative;
}
.health-num {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 36px; font-weight: 800;
}
.health-factors {
  display: flex; flex-direction: column; gap: 6px;
}
.hf-item {
  font-size: 12px; color: var(--text-2); display: flex; align-items: center; gap: 8px;
}
.hf-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }

/* 热榜双栏 */
.double-panel {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;
}
.panel-card {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 22px 24px; box-shadow: var(--shadow);
}
.pc-title { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 14px; }
.rank-list { display: flex; flex-direction: column; gap: 6px; }
.rank-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-radius: 8px;
  transition: all 0.15s; font-size: 13px;
}
.rank-item:hover { background: var(--bg-page); }
.rank-num {
  width: 24px; height: 24px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
  background: var(--bg-page); color: var(--text-3);
}
.rank-num.r1 { background: var(--primary-soft); color: var(--primary); }
.rank-num.r2 { background: var(--green-soft); color: var(--green); }
.rank-num.r3 { background: var(--orange); color: var(--text-inverse); opacity: 0.7; }
.rank-name {
  flex: 1; color: var(--text-1); font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.rank-sub  { color: var(--text-3); font-size: 12px; }
.rank-val  { font-weight: 600; font-size: 12px; }

@media (max-width: 768px) {
  .insight-grid, .double-panel { grid-template-columns: 1fr; }
}
</style>
