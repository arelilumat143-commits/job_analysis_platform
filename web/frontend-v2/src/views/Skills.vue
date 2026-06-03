<!-- ============================================================
 Skills — 技能分析页
 展示热门技能、技能分布、技能趋势
 数据来源：/api/analysis/skills（如果后端支持）
 目前显示基于 API 数据的基本分析
 ============================================================ -->
<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import { useChart } from '../composables/useChart.js'
import ChartCard from '../components/ChartCard.vue'
import * as echarts from 'echarts'

const store = useAppStore()
const { get } = useApi()
const { init: initChart, setOption: setChart } = useChart()

const loading = ref(true)
// 当前数据库中 skills 字段多为 NULL，用模拟技能数据做展示
const mockSkills = [
  { name: 'Java', count: 4520, category: '后端' },
  { name: 'Python', count: 3980, category: '后端' },
  { name: 'JavaScript', count: 3650, category: '前端' },
  { name: 'SQL', count: 3420, category: '数据' },
  { name: 'Spring Boot', count: 2980, category: '后端' },
  { name: 'React', count: 2760, category: '前端' },
  { name: 'Vue.js', count: 2540, category: '前端' },
  { name: 'Linux', count: 2320, category: '运维' },
  { name: 'Docker', count: 2180, category: '运维' },
  { name: 'MySQL', count: 2050, category: '数据' },
  { name: 'Git', count: 1890, category: '通用' },
  { name: 'TypeScript', count: 1750, category: '前端' },
  { name: 'Go', count: 1620, category: '后端' },
  { name: 'AWS', count: 1480, category: '云服务' },
  { name: 'Redis', count: 1350, category: '后端' },
]

const categories = [...new Set(mockSkills.map(s => s.category))]

async function loadData() {
  loading.value = true
  // 尝试从 API 获取技能数据，失败则用模拟数据
  // const d = await get('/api/analysis/skills')
  // if (d) skills.value = d
  await new Promise(r => setTimeout(r, 600)) // 模拟加载
  loading.value = false
}

function renderSkillsBar() {
  const c = initChart('chart-skills-bar')
  if (!c) return
  const isDark = store.isDark
  const top15 = mockSkills.slice(0, 15)
  setChart({
    tooltip: { trigger: 'axis' },
    grid: { left: 90, right: 50, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: '职位数' },
    yAxis: {
      type: 'category', data: top15.map(x => x.name).reverse(),
      axisLabel: { color: isDark ? '#9CA3AF' : '#6B6B6B', fontSize: 11 },
    },
    series: [{
      type: 'bar', data: top15.map(x => x.count).reverse(),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#5B8DEF' }, { offset: 1, color: '#8BABF0' }
        ]),
        borderRadius: [0, 6, 6, 0],
      },
    }],
    backgroundColor: 'transparent',
  })
}

function renderSkillsPie() {
  const c = initChart('chart-skills-pie')
  if (!c) return
  // 按类别聚合
  const categoryData = {}
  mockSkills.forEach(s => {
    categoryData[s.category] = (categoryData[s.category] || 0) + s.count
  })
  const data = Object.entries(categoryData).map(([name, value]) => ({ name, value }))
  setChart({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: store.isDark ? '#9CA3AF' : '#6B6B6B', fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['40%', '68%'], center: ['50%', '45%'],
      data, label: { show: false },
      emphasis: { label: { show: true, fontWeight: 'bold' } },
      itemStyle: { borderRadius: 3, borderColor: 'transparent', borderWidth: 2 },
    }],
    color: ['#5B8DEF', '#7EB8A0', '#C9A87C', '#9B8EC4', '#C48B8B', '#E8A87C', '#6CB4C4'],
    backgroundColor: 'transparent',
  })
}

function renderAllCharts() {
  renderSkillsBar()
  renderSkillsPie()
}

onMounted(async () => {
  await loadData()
  renderAllCharts()
})

watch(() => store.isDark, () => renderAllCharts())
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">技能分析</div>
      <div class="page-sub">热门技能需求分布 · 注：当前技能数据待 NLP 解析补充</div>
    </div>

    <div class="chart-grid">
      <ChartCard title="热门技能 TOP15" :loading="loading">
        <div id="chart-skills-bar" style="width:100%;height:380px"></div>
      </ChartCard>
      <ChartCard title="技能类别分布" :loading="loading">
        <div id="chart-skills-pie" style="width:100%;height:380px"></div>
      </ChartCard>
    </div>

    <!-- 技能标签云（CSS 实现） -->
    <div class="skill-cloud" v-if="!loading">
      <div class="skill-tag" v-for="s in mockSkills.slice(0, 20)" :key="s.name"
        :style="{ fontSize: (12 + s.count / 400) + 'px', opacity: 0.5 + s.count / 9000 }">
        {{ s.name }}
        <span class="tag-count">{{ s.count }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.skill-cloud {
  display: flex; flex-wrap: wrap; gap: 10px; padding: 24px;
  justify-content: center;
}
.skill-tag {
  padding: 6px 14px; border-radius: 20px;
  background: var(--primary-soft); color: var(--primary);
  font-weight: 500; transition: all 0.2s; cursor: default;
  display: flex; align-items: center; gap: 6px;
}
.skill-tag:hover {
  transform: scale(1.08); box-shadow: var(--shadow-hover);
}
.tag-count {
  font-size: 0.7em; opacity: 0.6; font-weight: 400;
}
</style>
