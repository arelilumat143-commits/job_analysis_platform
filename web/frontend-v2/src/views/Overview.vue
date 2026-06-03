<!-- ============================================================
 Overview — 首页概览仪表盘
 4 个指标卡片 + 4 个图表（城市柱状图/薪资直方图/来源饼图/行业柱状图）
 数据来源：/api/jobs/stats + /api/analysis/salary
 图表联动：点击城市柱 → Pinia selectedCity → 薪资图表联动
 ============================================================ -->
<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import { useChart } from '../composables/useChart.js'
import MetricCard from '../components/MetricCard.vue'
import ChartCard from '../components/ChartCard.vue'
import * as echarts from 'echarts'

const store = useAppStore()
const { get } = useApi()
const { init: initChart, setOption: setChart } = useChart()

// ---- 状态 ----
const loading = ref(true)
const stats = ref(null)     // /api/jobs/stats 返回的统计数据
const salaryData = ref(null) // /api/analysis/salary 返回的薪资分析

// ---- 计算派生指标 ----
const avgSalary = computed(() => {
  if (!salaryData.value) return '--'
  return salaryData.value.basic_stats?.mean?.toFixed(1) + 'K' || '--'
})
const topCity = computed(() => {
  if (!stats.value?.by_city?.length) return '--'
  return stats.value.by_city[0].city
})
const topSource = computed(() => {
  if (!stats.value?.by_source?.length) return '--'
  const s = stats.value.by_source[0]
  const map = { zhilian: '智联', boss: 'BOSS', lagou: '拉勾' }
  return (map[s.source] || s.source) + ' ' + s.count + '条'
})

// ---- 加载数据 ----
async function loadData() {
  loading.value = true
  // 先读缓存
  if (store.statsCache && store.isCacheValid(store.statsCacheTime)) {
    stats.value = store.statsCache
  } else {
    const d = await get('/api/jobs/stats')
    if (d) {
      stats.value = d
      store.statsCache = d
      store.statsCacheTime = Date.now()
    }
  }
  const s = await get('/api/analysis/salary')
  if (s) salaryData.value = s
  loading.value = false
}

// ---- 图表渲染 ----
function renderCityChart() {
  const c = initChart('chart-city')
  if (!c || !stats.value?.by_city) return
  const cities = stats.value.by_city.slice(0, 10)
  // 响应暗色主题
  const isDark = store.isDark
  setChart({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 10, bottom: 40 },
    xAxis: {
      type: 'category', data: cities.map(x => x.city),
      axisLabel: { rotate: 30, color: isDark ? '#9CA3AF' : '#6B6B6B' },
    },
    yAxis: { type: 'value', name: '职位数' },
    series: [{
      type: 'bar', data: cities.map(x => x.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#5B8DEF' }, { offset: 1, color: '#8BABF0' }
        ]),
        borderRadius: [6, 6, 0, 0],
      },
      emphasis: { itemStyle: { color: '#4A7BE0' } },
    }],
    backgroundColor: 'transparent',
  })
  // 点击城市 → 联动 Pinia store
  c.off('click')
  c.on('click', (params) => {
    store.selectCity(params.name)
  })
}

function renderSalaryChart() {
  const c = initChart('chart-salary')
  if (!c || !salaryData.value?.distribution) return
  const dist = salaryData.value.distribution
  const isDark = store.isDark
  setChart({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 10, bottom: 40 },
    xAxis: {
      type: 'category', data: dist.map(x => x.range),
      axisLabel: { rotate: 30, fontSize: 10, color: isDark ? '#9CA3AF' : '#6B6B6B' },
    },
    yAxis: { type: 'value', name: '职位数' },
    series: [{
      type: 'bar', data: dist.map(x => x.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#7EB8A0' }, { offset: 1, color: '#A8D5C0' }
        ]),
        borderRadius: [6, 6, 0, 0],
      },
    }],
    backgroundColor: 'transparent',
  })
}

function renderSourceChart() {
  const c = initChart('chart-source')
  if (!c || !stats.value?.by_source) return
  const data = stats.value.by_source.map(x => ({
    name: { zhilian: '智联招聘', boss: 'BOSS直聘', lagou: '拉勾网' }[x.source] || x.source,
    value: x.count,
  }))
  setChart({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: store.isDark ? '#9CA3AF' : '#6B6B6B' } },
    series: [{
      type: 'pie', radius: ['45%', '70%'], center: ['50%', '48%'],
      data, label: { show: false },
      emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
      itemStyle: { borderRadius: 4, borderColor: 'transparent', borderWidth: 2 },
    }],
    backgroundColor: 'transparent',
  })
}

function renderIndustryChart() {
  const c = initChart('chart-industry')
  if (!c || !stats.value?.by_industry) return
  const data = stats.value.by_industry.filter(x => x.industry !== '未知').slice(0, 10)
  if (!data.length) {
    // 全是"未知"时显示提示
    setChart({
      title: { text: '行业数据暂未采集', left: 'center', top: 'center',
        textStyle: { color: store.isDark ? '#6B7280' : '#A0A0A0', fontSize: 14 }},
      backgroundColor: 'transparent',
    })
    return
  }
  const isDark = store.isDark
  setChart({
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: '职位数' },
    yAxis: {
      type: 'category', data: data.map(x => x.industry),
      axisLabel: { color: isDark ? '#9CA3AF' : '#6B6B6B' },
    },
    series: [{
      type: 'bar', data: data.map(x => x.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#9B8EC4' }, { offset: 1, color: '#B8AEE0' }
        ]),
        borderRadius: [0, 6, 6, 0],
      },
    }],
    backgroundColor: 'transparent',
  })
}

function renderAllCharts() {
  renderCityChart()
  renderSalaryChart()
  renderSourceChart()
  renderIndustryChart()
}

// ---- 生命周期 ----
onMounted(async () => {
  await loadData()
  renderAllCharts()
})

// 暗色模式切换时重新渲染
watch(() => store.isDark, () => {
  renderAllCharts()
})

// 选中城市变化 → 重新加载薪资数据
watch(() => store.selectedCity, (city) => {
  if (city) {
    // 可以通过 API 参数过滤城市数据，这里先做简单联动
    console.log('[Overview] 选中城市:', city)
  }
})
</script>

<template>
  <div class="page">
    <!-- Hero 区域 -->
    <div class="page-hero">
      <div class="page-title">首页概览</div>
      <div class="page-sub">招聘市场实时数据总览 · 共 {{ stats?.total?.toLocaleString() || '--' }} 条职位</div>
    </div>

    <!-- 指标卡片 -->
    <div class="metrics-grid">
      <MetricCard icon="◉" :value="stats?.total || 0" label="职位总数" :loading="loading" />
      <MetricCard icon="◆" :value="avgSalary" label="平均薪资(K)" :loading="loading" />
      <MetricCard icon="●" :value="topCity" label="职位最多城市" :loading="loading" />
      <MetricCard icon="▲" :value="topSource" label="主要数据来源" :loading="loading" />
    </div>

    <!-- 图表区域 -->
    <div class="chart-grid">
      <ChartCard title="各城市职位分布 (点击联动)" :loading="loading">
        <div id="chart-city" style="width:100%;height:320px"></div>
      </ChartCard>
      <ChartCard title="薪资区间分布" :loading="loading">
        <div id="chart-salary" style="width:100%;height:320px"></div>
      </ChartCard>
      <ChartCard title="数据来源占比" :loading="loading">
        <div id="chart-source" style="width:100%;height:320px"></div>
      </ChartCard>
      <ChartCard title="行业分布" :loading="loading">
        <div id="chart-industry" style="width:100%;height:320px"></div>
      </ChartCard>
    </div>
  </div>
</template>

<style scoped>
/* 复用 DefaultLayout 的共享样式（page-hero/metrics-grid/chart-grid） */
</style>
