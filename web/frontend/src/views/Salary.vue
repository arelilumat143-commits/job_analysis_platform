<!-- ============================================================
 Salary v2 — 薪资分析页（多维度对比增强版）
 新增：教育-薪资分析 / 多维对比 / 优化预测面板
 数据来源：/api/analysis/salary + /api/analysis/education + /api/prediction/salary
 ============================================================ -->
<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import { useChart } from '../composables/useChart.js'
import MetricCard from '../components/MetricCard.vue'
import ChartCard from '../components/ChartCard.vue'
import * as echarts from 'echarts'

const store = useAppStore()
const { get, post } = useApi()
const { init: initChart, setOption: setChart, readCssVar } = useChart()

const loading = ref(true)
const salaryData = ref(null)
const educationData = ref(null)
const industryData = ref(null)

// ---- 薪资预测 ----
const predictForm = ref({
  city: '北京', experience_years: 3.0,
  skills: 'Python,Django,MySQL', education: '本科',
})
const predicting = ref(false)
const predictResult = ref(null)
const predictError = ref('')

// ---- 统计摘要 ----
const statsSummary = computed(() => {
  const s = salaryData.value?.basic_stats
  if (!s) return []
  return [
    { icon: '◆', value: s.mean?.toFixed(1) + 'K', label: '平均薪资' },
    { icon: '◈', value: s.median?.toFixed(1) + 'K', label: '中位数' },
    { icon: '◆', value: s.q25?.toFixed(1) + 'K', label: '25分位' },
    { icon: '◆', value: s.q75?.toFixed(1) + 'K', label: '75分位' },
  ]
})

const cities = ['北京', '上海', '广州', '深圳', '杭州', '成都', '南京', '武汉', '西安', '郑州']
const educations = ['本科', '硕士', '大专', '博士', '高中', '中专/中技']

// ---- 多维对比数据 ----
const comparisonData = computed(() => {
  const items = []
  if (salaryData.value?.by_city?.length) {
    const top = salaryData.value.by_city.slice(0, 5)
    items.push({ title: '城市薪资对比', data: top.map(x => ({ label: x.city, value: x.avg_salary.toFixed(1) + 'K', sub: x.count + '条' })) })
  }
  if (salaryData.value?.by_experience?.length) {
    const exp = salaryData.value.by_experience.filter(x => x.experience !== '不限').slice(0, 5)
    items.push({ title: '经验薪资对比', data: exp.map(x => ({ label: x.experience, value: x.avg_salary.toFixed(1) + 'K', sub: x.count + '条' })) })
  }
  if (educationData?.length) {
    const edu = educationData.slice(0, 5)
    items.push({ title: '学历薪资对比', data: edu.map(x => ({ label: x.education, value: x.avg_salary ? x.avg_salary.toFixed(1) + 'K' : '--', sub: x.count + '条' })) })
  }
  return items
})

// ---- 预测 ----
async function runPrediction() {
  predictError.value = ''
  predictResult.value = null
  predicting.value = true
  const skillsArray = predictForm.value.skills.split(/[,，、;；]/).map(s => s.trim()).filter(s => s.length > 0)
  if (!skillsArray.length) { predictError.value = '请至少输入一个技能'; predicting.value = false; return }
  const result = await post('/api/prediction/salary', {
    city: predictForm.value.city, experience_years: predictForm.value.experience_years,
    skills: skillsArray, education: predictForm.value.education,
  })
  if (result) predictResult.value = result
  else predictError.value = '预测失败，请检查后端服务'
  predicting.value = false
}

function factorDirection(impact) {
  if (impact > 0) return { cls: 'up', sign: '+' }
  if (impact < 0) return { cls: 'down', sign: '' }
  return { cls: '', sign: '' }
}

function confidenceColor(conf) {
  if (conf >= 0.8) return 'var(--green)'
  if (conf >= 0.6) return 'var(--orange)'
  return 'var(--red)'
}

// ---- 加载数据 ----
async function loadData() {
  loading.value = true
  const [d, edu, ind] = await Promise.all([
    get('/api/analysis/salary'),
    get('/api/analysis/education'),
    get('/api/analysis/industry'),
  ])
  if (d) salaryData.value = d
  if (edu) educationData.value = edu
  if (ind) industryData.value = ind
  loading.value = false
}

// ---- 图表 ----
function renderCitySalaryChart() {
  const c = initChart('chart-city-salary')
  if (!c || !salaryData.value?.by_city) return
  const data = salaryData.value.by_city.slice(0, 10)
  setChart('chart-city-salary', {
    tooltip: { trigger: 'axis', formatter: p => p[0].name + '<br/>均薪: ' + p[0].value + 'K' },
    grid: { left: 50, right: 20, top: 10, bottom: 50 },
    xAxis: { type: 'category', data: data.map(x => x.city), axisLabel: { rotate: 30, color: readCssVar('--text-2') } },
    yAxis: { type: 'value', name: '均薪(K)' },
    series: [{
      type: 'bar', data: data.map(x => +x.avg_salary.toFixed(1)),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: readCssVar('--orange') }, { offset: 1, color: readCssVar('--orange-light') }
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
  setChart('chart-distribution', {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 60, top: 20, bottom: 40 },
    legend: { data: ['职位数', '占比'], bottom: 0, textStyle: { color: readCssVar('--text-2') } },
    xAxis: { type: 'category', data: dist.map(x => x.range), axisLabel: { rotate: 30, fontSize: 10, color: readCssVar('--text-2') } },
    yAxis: [
      { type: 'value', name: '职位数', axisLabel: { color: readCssVar('--text-2') } },
      { type: 'value', name: '占比(%)', axisLabel: { formatter: '{value}%', color: readCssVar('--text-2') } },
    ],
    series: [
      { type: 'bar', name: '职位数', data: dist.map(x => x.count),
        itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: readCssVar('--green') }, { offset: 1, color: readCssVar('--green-light') }]), borderRadius: [6, 6, 0, 0] } },
      { type: 'line', name: '占比', yAxisIndex: 1, data: dist.map(x => +(x.percentage || 0).toFixed(1)), smooth: true,
        lineStyle: { color: readCssVar('--primary'), width: 2 }, itemStyle: { color: readCssVar('--primary') }, symbol: 'circle', symbolSize: 6 },
    ],
    backgroundColor: 'transparent',
  })
}

function renderExperienceChart() {
  const c = initChart('chart-experience')
  if (!c || !salaryData.value?.by_experience) return
  const data = salaryData.value.by_experience.filter(x => x.experience !== '不限')
  if (!data.length) {
    setChart('chart-experience', {
      title: { text: '经验数据待采集', subtext: '需运行爬虫抓取职位详情页', left: 'center', top: 'center',
        textStyle: { color: readCssVar('--text-3') }, subtextStyle: { color: readCssVar('--text-3') }},
      backgroundColor: 'transparent',
    })
    return
  }
  setChart('chart-experience', {
    tooltip: { trigger: 'axis', formatter: p => p[0].name + '<br/>均薪: ' + p[0].value + 'K' },
    grid: { left: 80, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: '均薪(K)' },
    yAxis: { type: 'category', data: data.map(x => x.experience), axisLabel: { color: readCssVar('--text-2') } },
    series: [{
      type: 'bar', data: data.map(x => +x.avg_salary.toFixed(1)),
      itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: readCssVar('--purple') }, { offset: 1, color: readCssVar('--purple-light') }]), borderRadius: [0, 6, 6, 0] },
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
  await nextTick()
  renderAllCharts()
})

watch(() => store.isDark, () => renderAllCharts())
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">薪资分析</div>
      <div class="page-sub">基于 {{ salaryData?.basic_stats?.count?.toLocaleString() || '--' }} 条有薪资数据的职位分析</div>
    </div>

    <!-- 指标卡 -->
    <div class="metrics-grid">
      <MetricCard v-for="m in statsSummary" :key="m.label" :icon="m.icon" :value="m.value" :label="m.label" :loading="loading" />
    </div>

    <!-- ===== 薪资预测面板 ===== -->
    <div class="predict-panel">
      <div class="panel-header">
        <span class="panel-title">薪资预测</span>
        <span class="panel-desc">XGBoost 模型 — 基于 2,300+ 真实样本训练</span>
      </div>
      <div class="predict-form">
        <div class="form-group"><label>城市</label>
          <select v-model="predictForm.city" class="form-input">
            <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="form-group"><label>经验年限</label>
          <input v-model.number="predictForm.experience_years" type="number" step="0.5" min="0" max="50" class="form-input" />
        </div>
        <div class="form-group"><label>学历</label>
          <select v-model="predictForm.education" class="form-input">
            <option v-for="e in educations" :key="e" :value="e">{{ e }}</option>
          </select>
        </div>
        <div class="form-group" style="flex:2; min-width:220px"><label>技能</label>
          <input v-model="predictForm.skills" class="form-input" placeholder="Python,Django,MySQL,Redis" />
        </div>
        <button class="predict-btn" @click="runPrediction" :disabled="predicting">
          {{ predicting ? '预测中...' : '开始预测' }}
        </button>
      </div>

      <div v-if="predictResult" class="predict-result">
        <div class="result-main">
          <div class="salary-display">
            <div class="salary-label">预测月薪</div>
            <div class="salary-value">
              <span class="sal-min">{{ predictResult.prediction.salary_min }}</span>
              <span class="sal-sep">-</span>
              <span class="sal-mid">{{ predictResult.prediction.salary_avg }}</span>
              <span class="sal-sep">-</span>
              <span class="sal-max">{{ predictResult.prediction.salary_max }}</span>
              <span class="sal-unit">K/月</span>
            </div>
          </div>
          <div class="confidence-badge" :style="{ background: confidenceColor(predictResult.confidence) }">
            置信度 {{ (predictResult.confidence * 100).toFixed(0) }}%
          </div>
        </div>
        <div v-if="predictResult.factors?.length" class="factors-section">
          <div class="factors-title">影响因素分析</div>
          <div class="factors-grid">
            <div v-for="f in predictResult.factors" :key="f.factor" class="factor-item">
              <div class="factor-name">{{ f.factor.split(':')[1] || f.factor }}</div>
              <div class="factor-impact" :class="factorDirection(f.impact).cls">
                {{ factorDirection(f.impact).sign }}{{ f.impact > 0 ? '+' : '' }}{{ f.impact }}K
              </div>
              <div class="factor-desc">{{ f.explanation }}</div>
            </div>
          </div>
        </div>
        <div class="model-version">模型版本: {{ predictResult.model_version }}</div>
      </div>
      <div v-if="predictError" class="predict-error">{{ predictError }}</div>
    </div>

    <!-- ===== 多维度对比 ===== -->
    <div class="comparison-section" v-if="comparisonData.length">
      <h3 class="section-title">多维度薪资对比</h3>
      <div class="comparison-grid">
        <div class="comp-card" v-for="col in comparisonData" :key="col.title">
          <div class="comp-title">{{ col.title }}</div>
          <div class="comp-list">
            <div class="comp-item" v-for="(item, i) in col.data" :key="item.label">
              <span class="comp-rank" :class="'r' + (i + 1)">{{ i + 1 }}</span>
              <span class="comp-label">{{ item.label }}</span>
              <span class="comp-value">{{ item.value }}</span>
              <span class="comp-sub">{{ item.sub }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 图表区 ===== -->
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
/* 预测面板 */
.predict-panel { background: var(--bg-card); border-radius: var(--radius); padding: 24px; margin-bottom: 24px; box-shadow: var(--shadow); border: 1px solid var(--border); }
.panel-header { margin-bottom: 16px; }
.panel-title { font-size: 17px; font-weight: 600; color: var(--text-1); margin-right: 10px; }
.panel-desc  { font-size: 13px; color: var(--text-3); }
.predict-form { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
.form-group { flex: 1; min-width: 120px; }
.form-group label { display: block; font-size: 12px; color: var(--text-3); margin-bottom: 4px; font-weight: 500; }
.form-input { width: 100%; padding: 9px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-page); color: var(--text-1); font-size: 14px; outline: none; }
.form-input:focus { border-color: var(--primary); }
.predict-btn { padding: 10px 24px; border-radius: var(--radius-sm); border: none; background: var(--primary); color: var(--text-inverse); font-size: 14px; font-weight: 500; cursor: pointer; white-space: nowrap; height: 40px; transition: all 0.2s; }
.predict-btn:hover:not(:disabled) { opacity: 0.9; }
.predict-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.predict-result { margin-top: 20px; padding: 20px; background: var(--bg-page); border-radius: var(--radius-sm); border: 1px solid var(--border); }
.result-main { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
.salary-display { text-align: center; flex: 1; }
.salary-label { font-size: 12px; color: var(--text-3); margin-bottom: 4px; }
.salary-value { font-size: 28px; font-weight: 700; color: var(--text-1); }
.sal-min  { color: var(--primary); }
.sal-mid  { color: var(--orange); font-size: 36px; }
.sal-max  { color: var(--green); }
.sal-sep  { color: var(--text-3); margin: 0 4px; font-size: 20px; }
.sal-unit { font-size: 14px; color: var(--text-3); margin-left: 6px; }
.confidence-badge { padding: 8px 20px; border-radius: 20px; color: var(--text-inverse); font-size: 14px; font-weight: 600; }

.factors-section { margin-top: 16px; }
.factors-title { font-size: 13px; font-weight: 600; color: var(--text-2); margin-bottom: 10px; }
.factors-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.factor-item { padding: 12px; background: var(--bg-card); border-radius: var(--radius-sm); border: 1px solid var(--border); }
.factor-name  { font-size: 13px; font-weight: 600; color: var(--text-1); margin-bottom: 2px; }
.factor-impact { font-size: 16px; font-weight: 700; margin-bottom: 2px; }
.factor-impact.up   { color: var(--green); }
.factor-impact.down { color: var(--red); }
.factor-desc  { font-size: 11px; color: var(--text-3); line-height: 1.4; }
.model-version { margin-top: 10px; font-size: 11px; color: var(--text-3); text-align: right; }
.predict-error { margin-top: 12px; padding: 10px 14px; border-radius: var(--radius-sm); background: var(--red-soft); color: var(--red); font-size: 13px; }

/* 多维对比 */
.comparison-section { margin-bottom: 24px; }
.section-title { font-size: 16px; font-weight: 600; color: var(--text-1); margin-bottom: 14px; }
.comparison-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.comp-card { background: var(--bg-card); border-radius: var(--radius-sm); padding: 18px 20px; box-shadow: var(--shadow); }
.comp-title { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 12px; }
.comp-list { display: flex; flex-direction: column; gap: 8px; }
.comp-item { display: flex; align-items: center; gap: 8px; }
.comp-rank { width: 22px; height: 22px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; background: var(--bg-page); color: var(--text-3); }
.comp-rank.r1 { background: var(--primary-soft); color: var(--primary); }
.comp-rank.r2 { background: var(--green-soft); color: var(--green); }
.comp-rank.r3 { background: var(--orange); color: var(--text-inverse); opacity: 0.7; }
.comp-label { flex: 1; font-size: 13px; color: var(--text-1); }
.comp-value { font-weight: 600; color: var(--primary); font-size: 14px; }
.comp-sub { font-size: 11px; color: var(--text-3); }

@media (max-width: 900px) {
  .comparison-grid { grid-template-columns: 1fr; }
}
</style>
