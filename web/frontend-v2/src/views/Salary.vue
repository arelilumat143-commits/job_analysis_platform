<!-- ============================================================
 Salary — 薪资分析页
 图表：城市平均薪资柱状图 / 经验-薪资关系 / 学历-薪资关系
 数据来源：/api/analysis/salary
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

const loading = ref(true)
const salaryData = ref(null)

// 薪资统计摘要
const statsSummary = computed(() => {
  const s = salaryData.value?.basic_stats
  if (!s) return []
  return [
    { icon: '◆', value: s.mean?.toFixed(1) + 'K', label: '平均薪资' },
    { icon: '◈', value: s.median?.toFixed(1) + 'K', label: '中位数薪资' },
    { icon: '◆', value: s.q25?.toFixed(1) + 'K', label: '25分位' },
    { icon: '◆', value: s.q75?.toFixed(1) + 'K', label: '75分位' },
  ]
})

async function loadData() {
  loading.value = true
  const d = await get('/api/analysis/salary')
  if (d) salaryData.value = d
  loading.value = false
}

function renderCitySalaryChart() {
  const c = initChart('chart-city-salary')
  if (!c || !salaryData.value?.by_city) return
  const data = salaryData.value.by_city.slice(0, 10)
  const isDark = store.isDark
  setChart({
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>平均薪资: ${p[0].value}K` },
    grid: { left: 50, right: 20, top: 10, bottom: 50 },
    xAxis: {
      type: 'category', data: data.map(x => x.city),
      axisLabel: { rotate: 30, color: isDark ? '#9CA3AF' : '#6B6B6B' },
    },
    yAxis: { type: 'value', name: '平均薪资(K)', axisLabel: { formatter: '{value}K' } },
    series: [{
      type: 'bar', data: data.map(x => +x.avg_salary.toFixed(1)),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#C9A87C' }, { offset: 1, color: '#E0C9A0' }
        ]),
        borderRadius: [6, 6, 0, 0],
      },
    }],
    backgroundColor: 'transparent',
  })
}

function renderDistributionChart() {
  const c = initChart('chart-distribution')
  if (!c || !salaryData.value?.distribution) return
  const dist = salaryData.value.distribution
  const isDark = store.isDark
  setChart({
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category', data: dist.map(x => x.range),
      axisLabel: { rotate: 30, fontSize: 10, color: isDark ? '#9CA3AF' : '#6B6B6B' },
    },
    yAxis: { type: 'value', name: '职位数' },
    series: [
      {
        type: 'bar', name: '职位数', data: dist.map(x => x.count),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#7EB8A0' }, { offset: 1, color: '#A8D5C0' }
          ]),
          borderRadius: [6, 6, 0, 0],
        },
      },
      {
        type: 'line', name: '占比', yAxisIndex: 1,
        data: dist.map(x => +(x.percentage || 0).toFixed(1)),
        smooth: true,
        lineStyle: { color: '#5B8DEF', width: 2 },
        itemStyle: { color: '#5B8DEF' },
        symbol: 'circle', symbolSize: 6,
      },
    ],
    backgroundColor: 'transparent',
  })
}

function renderExperienceChart() {
  const c = initChart('chart-experience')
  if (!c || !salaryData.value?.by_experience) return
  const data = salaryData.value.by_experience
  const isDark = store.isDark
  setChart({
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>平均薪资: ${p[0].value}K` },
    grid: { left: 80, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: '平均薪资(K)' },
    yAxis: {
      type: 'category', data: data.map(x => x.experience),
      axisLabel: { color: isDark ? '#9CA3AF' : '#6B6B6B' },
    },
    series: [{
      type: 'bar', data: data.map(x => +x.avg_salary.toFixed(1)),
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
  renderCitySalaryChart()
  renderDistributionChart()
  renderExperienceChart()
}

onMounted(async () => {
  await loadData()
  renderAllCharts()
})

watch(() => store.isDark, () => renderAllCharts())
watch(() => store.selectedCity, (city) => {
  if (city) console.log('[Salary] 联动城市:', city)
})
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">薪资分析</div>
      <div class="page-sub">基于 {{ salaryData?.basic_stats?.count || '--' }} 条有薪资数据的职位分析</div>
    </div>

    <!-- 薪资指标卡片 -->
    <div class="metrics-grid">
      <MetricCard v-for="m in statsSummary" :key="m.label"
        :icon="m.icon" :value="m.value" :label="m.label" :loading="loading" />
    </div>

    <!-- 图表 -->
    <div class="chart-grid">
      <ChartCard title="各城市平均薪资" :loading="loading">
        <div id="chart-city-salary" style="width:100%;height:320px"></div>
      </ChartCard>
      <ChartCard title="薪资区间分布" :loading="loading">
        <div id="chart-distribution" style="width:100%;height:320px"></div>
      </ChartCard>
      <ChartCard title="经验-薪资关系" :loading="loading">
        <div id="chart-experience" style="width:100%;height:320px"></div>
      </ChartCard>
    </div>
  </div>
</template>

<style scoped>
</style>
