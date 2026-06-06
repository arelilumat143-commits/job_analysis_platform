<script setup>
// ============================================================
// 招聘分析平台 — 主组件（重构版）
// 改动：组件化 MetricCard/ChartCard | useChart 封装 | CountUp 动画 | Skeleton 加载
// ============================================================
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import MetricCard from './components/MetricCard.vue'
import ChartCard from './components/ChartCard.vue'
import { useChart } from './composables/useChart.js'

// ============================================================
// 莫兰迪配色常量（供 ECharts setOption 使用）
// ============================================================
const C = {
  primary:      '#5B8DEF',
  primaryLight: '#8BABF0',
  primarySoft:  '#EEF2FB',
  green:        '#7EB8A0',
  greenSoft:    '#EEF5F1',
  purple:       '#9B8EC4',
  orange:       '#C9A87C',
  text1:        '#2C2C2C',
  text2:        '#6B6B6B',
  text3:        '#A0A0A0',
  chartColors:  ['#5B8DEF','#7EB8A0','#9B8EC4','#C9A87C','#8BABF0','#A8D0C0','#B8AED8','#D4BC9A'],
  chartBlues:   ['#EEF2FB','#D4E0F8','#A8C2F2','#7BA6EC','#5B8DEF'],
  chartGreens:  ['#EDF5F1','#D4EBE2','#A8D8C4','#7EC5A6','#5EB28E'],
}

// ============================================================
// 状态
// ============================================================
const currentPage = ref('overview')  // 当前 Tab
const loading = ref(true)            // 全局加载态（首次进入显示骨架屏）

// ============================================================
// 图表实例（每个图表一个 useChart，各自管理生命周期）
// ============================================================
const cityChart     = useChart()
const salaryHist    = useChart()
const sourcePie     = useChart()
const industryBar   = useChart()

// ============================================================
// 模拟数据（后续替换为 API 请求）
// ============================================================
const metrics = {
  totalJobs: 22588,
  avgSalary: '18.5 K',
  topCity:   '成都',
  topSkill:  'Python',
}
const cityData = [
  ['北京',3200],['成都',2800],['上海',2200],['深圳',1900],
  ['杭州',1600],['武汉',1400],['广州',1200],['南京',950],['西安',820],['郑州',700],
]
const sourceData = [
  {name:'智联招聘',value:22583},{name:'BOSS直聘',value:180},{name:'拉勾',value:50},{name:'其他',value:18},
]
const industryData = [
  ['互联网',2100],['人工智能',650],['金融',420],['电商',380],
  ['教育',280],['医疗',200],['游戏',170],['制造业',130],
]
// 薪资直方图模拟数据（x: 区间, y: 占比%）
const salaryBins      = ['0-5','5-10','10-15','15-20','20-25','25-30','30-35','35-40','40+']
const salaryBinValues = [2, 5, 8, 12, 7, 4, 1, 1, 0]

// ============================================================
// 职位搜索 — 筛选状态 + 模拟数据
// ============================================================
const searchKeyword  = ref('')       // 搜索关键词
const searchCity     = ref('')       // 城市筛选（空=全部）
const searchExp      = ref('')       // 经验要求筛选
const searchSalaryMin = ref(0)       // 最低薪资筛选

// 模拟职位库（30 条，后续接 API 替换）
const allJobs = Array.from({ length: 30 }, (_, i) => {
  const cities     = ['北京','成都','上海','深圳','杭州','武汉','广州','南京','西安','郑州']
  const titles     = ['Python开发工程师','Java后端开发','前端工程师','数据分析师','算法工程师','运维开发','测试工程师','产品经理','UI设计师','全栈工程师']
  const companies  = ['字节跳动','阿里巴巴','腾讯','华为','美团','京东','百度','网易','小米','滴滴']
  const exps       = ['应届生','1-3年','3-5年','5-10年','不限']
  const city       = cities[i % cities.length]
  const minSalary  = [5,8,10,12,15,18,20,25,30,35][i % 10]
  const maxSalary  = minSalary + [5,8,10,12,15,18,20,20,25,25][i % 10]
  return {
    id: i + 1,
    title: titles[i % titles.length],
    company: companies[i % companies.length],
    city,
    salary_min: minSalary,
    salary_max: maxSalary,
    experience: exps[i % exps.length],
    skills: ['Python','SQL','Linux','Docker','AWS'].slice(0, 2 + (i % 4)),
  }
})

// 计算筛选后的结果（computed 不是必须导入，这里用函数每次渲染时计算）
function getFilteredJobs() {
  let list = allJobs
  const kw = searchKeyword.value.toLowerCase()
  if (kw) {
    list = list.filter(j =>
      j.title.toLowerCase().includes(kw) ||
      j.company.toLowerCase().includes(kw) ||
      j.skills.some(s => s.toLowerCase().includes(kw))
    )
  }
  if (searchCity.value) {
    list = list.filter(j => j.city === searchCity.value)
  }
  if (searchExp.value) {
    list = list.filter(j => j.experience === searchExp.value)
  }
  if (searchSalaryMin.value > 0) {
    list = list.filter(j => j.salary_min >= searchSalaryMin.value)
  }
  return list
}

// 根据筛选结果重新计算时自动获取
function filteredJobs() {
  return getFilteredJobs()
}

// 城市列表（从模拟数据去重，后续接 API）
const allCities = [...new Set(allJobs.map(j => j.city))]
const expOptions = ['不限','应届生','1-3年','3-5年','5-10年']

// ============================================================
// 图表绘制函数（每个函数只管自己的图表）
// ============================================================
function drawCityChart() {
  cityChart.init('chart-cities')
  cityChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 10, top: 10, bottom: 20 },
    xAxis: {
      type: 'value',
      axisLabel: { color: C.text3, fontSize: 11 },
      splitLine: { lineStyle: { color: '#F5F5F5' } },
    },
    yAxis: {
      type: 'category',
      data: cityData.map(d => d[0]).reverse(),
      inverse: true,
      axisLabel: { color: C.text1, fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: cityData.map(d => d[1]).reverse(),
      barWidth: 16,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: C.chartBlues[0] },
          { offset: 1, color: C.chartBlues[4] },
        ]),
      },
    }],
  })
}

function drawSalaryHist() {
  salaryHist.init('chart-salary')
  salaryHist.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 10, top: 20, bottom: 20 },
    xAxis: {
      type: 'category',
      data: salaryBins,
      axisLabel: { color: C.text3, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: C.text3, fontSize: 11 },
      splitLine: { lineStyle: { color: '#F5F5F5' } },
    },
    series: [{
      type: 'bar',
      data: salaryBinValues,
      barWidth: '60%',
      itemStyle: { color: C.primary, borderRadius: [4, 4, 0, 0], opacity: 0.85 },
    }],
  })
}

function drawSourcePie() {
  sourcePie.init('chart-source')
  sourcePie.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['50%', '80%'],
      center: ['50%', '55%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 3 },
      label: { color: C.text2, fontSize: 12 },
      data: sourceData.map((d, i) => ({
        value: d.value,
        name: d.name,
        itemStyle: { color: C.chartColors[i] },
      })),
    }],
  })
}

function drawIndustryChart() {
  industryBar.init('chart-industry')
  industryBar.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 70, right: 10, top: 10, bottom: 20 },
    xAxis: { type: 'value', axisLabel: { color: C.text3, fontSize: 11 } },
    yAxis: {
      type: 'category',
      data: industryData.map(d => d[0]).reverse(),
      inverse: true,
      axisLabel: { color: C.text1, fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: industryData.map(d => d[1]).reverse(),
      barWidth: 16,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: C.chartGreens[1] },
          { offset: 1, color: C.chartGreens[4] },
        ]),
      },
    }],
  })
}

// ---- 统一绘制所有图表 ----
function drawAllCharts() {
  nextTick(() => {
    drawCityChart()
    drawSalaryHist()
    drawSourcePie()
    drawIndustryChart()
  })
}

// ============================================================
// 生命周期
// ============================================================
onMounted(() => {
  // 模拟数据加载：600ms 后关闭骨架屏，触发 CountUp
  setTimeout(() => { loading.value = false }, 600)
  drawAllCharts()
})

// 切换 Tab 时重新绘制（v-if 会销毁/重建 DOM）
watch(currentPage, (page) => {
  if (page === 'overview') drawAllCharts()
})
</script>

<!-- ============================================================
     TEMPLATE — 6 个 Tab 页面
     改动：指标卡用 <MetricCard>，图表用 <ChartCard>
============================================================ -->
<template>
  <!-- ========== 侧边栏 ========== -->
  <aside class="sidebar">
    <div class="brand">
      <div class="name">招聘分析平台</div>
      <div class="sub">Job Analytics</div>
    </div>

    <div class="db-badge">
      <span class="dot"></span>
      <span class="db-label">数据库</span>
      <span class="db-value">MYSQL</span>
    </div>

    <div class="nav-label">导航</div>
    <div
      class="nav-item"
      :class="{ active: currentPage === 'overview' }"
      @click="currentPage = 'overview'"
    >◉  首页概览</div>
    <div
      class="nav-item"
      :class="{ active: currentPage === 'salary' }"
      @click="currentPage = 'salary'"
    >◇  薪资分析</div>
    <div
      class="nav-item"
      :class="{ active: currentPage === 'skills' }"
      @click="currentPage = 'skills'"
    >○  技能分析</div>
    <div
      class="nav-item"
      :class="{ active: currentPage === 'recommend' }"
      @click="currentPage = 'recommend'"
    >□  岗位推荐</div>
    <div
      class="nav-item"
      :class="{ active: currentPage === 'data' }"
      @click="currentPage = 'data'"
    >△  数据管理</div>
    <div
      class="nav-item"
      :class="{ active: currentPage === 'ai' }"
      @click="currentPage = 'ai'"
    >▽  AI智能报告</div>
    <div
      class="nav-item"
      :class="{ active: currentPage === 'search' }"
      @click="currentPage = 'search'"
    >🔍  职位搜索</div>

    <div class="nav-spacer"></div>

    <div class="nav-label">系统</div>
    <div class="sys-info">
      <div class="sys-row"><span>项目</span><span>analysis_platform</span></div>
      <div class="sys-row"><span>数据库</span><span>job_analysis</span></div>
    </div>

    <button class="btn-refresh" @click="loading = true; setTimeout(() => loading = false, 600); drawAllCharts()">
      刷新数据缓存
    </button>

    <div class="version">v2.0 · Morandi Edition</div>
  </aside>

  <!-- ========== 主内容区 ========== -->
  <main class="main">

    <!-- ============================================================
         首页概览
    ============================================================ -->
    <template v-if="currentPage === 'overview'">
      <div class="hero">
        <div class="hero-title">首页概览</div>
        <div class="hero-sub">平台数据总览与核心指标一览，实时掌握招聘市场动态</div>
      </div>

      <!-- 指标卡片区域 —— 用 MetricCard 组件 -->
      <div class="metrics">
        <MetricCard icon="◉" :value="metrics.totalJobs" label="总职位数" :loading="loading" />
        <MetricCard icon="◇" :value="metrics.avgSalary" label="平均月薪" :loading="loading" />
        <MetricCard icon="○" :value="metrics.topCity"  label="热门城市" :loading="loading" />
        <MetricCard icon="□" :value="metrics.topSkill" label="热门技能" :loading="loading" />
      </div>

      <!-- 图表区域 —— 用 ChartCard 组件 -->
      <div class="chart-row">
        <ChartCard title="城市职位分布 Top 10" :loading="loading">
          <div id="chart-cities" class="chart-container" style="height:380px"></div>
        </ChartCard>
        <ChartCard title="薪资分布直方图" :loading="loading">
          <div id="chart-salary" class="chart-container" style="height:380px"></div>
        </ChartCard>
      </div>
      <div class="chart-row">
        <ChartCard title="招聘来源占比" :loading="loading">
          <div id="chart-source" class="chart-container" style="height:340px"></div>
        </ChartCard>
        <ChartCard title="行业分布 Top 8" :loading="loading">
          <div id="chart-industry" class="chart-container" style="height:340px"></div>
        </ChartCard>
      </div>
    </template>

    <!-- ============================================================
         薪资分析
    ============================================================ -->
    <template v-if="currentPage === 'salary'">
      <div class="hero">
        <div class="hero-title">薪资分析</div>
        <div class="hero-sub">各维度薪资对比与趋势分析，洞察市场薪酬水平</div>
      </div>
      <div class="metrics">
        <MetricCard icon="◇" value="18.5K" label="平均月薪" />
        <MetricCard icon="◎" value="15.0K" label="薪资中位数" />
        <MetricCard icon="◉" value="25.5K" label="75分位数" />
        <MetricCard icon="△" value="+8.2%" label="同比增长" />
      </div>
      <div class="chart-row chart-span">
        <ChartCard title="薪资分布直方图" :loading="loading">
          <div id="chart-salary-detail" class="chart-container" style="height:380px"></div>
        </ChartCard>
      </div>
    </template>

    <!-- ============================================================
         技能分析
    ============================================================ -->
    <template v-if="currentPage === 'skills'">
      <div class="hero">
        <div class="hero-title">技能分析</div>
        <div class="hero-sub">热门技能需求排行与趋势变化，把握技术方向</div>
      </div>
      <div class="chart-row chart-span">
        <ChartCard title="技能需求词云" :loading="loading">
          <!-- 手写词云占位 —— 待接入真实 NLP 数据 -->
          <div class="wordcloud">
            <span style="font-size:32px;color:var(--primary);font-weight:600">Python</span>
            <span style="font-size:28px;color:var(--green);font-weight:600">Java</span>
            <span style="font-size:26px;color:var(--purple);font-weight:600">SQL</span>
            <span style="font-size:24px;color:var(--orange);font-weight:600">JavaScript</span>
            <span style="font-size:22px;color:var(--primary);font-weight:500">React</span>
            <span style="font-size:20px;color:var(--green);font-weight:500">Linux</span>
            <span style="font-size:18px;color:var(--purple);font-weight:500">Docker</span>
            <span style="font-size:17px;color:var(--orange);font-weight:500">Git</span>
            <span style="font-size:16px;color:var(--primary-light);font-weight:500">K8s</span>
            <span style="font-size:15px;color:#A8D0C0;font-weight:500">AWS</span>
          </div>
        </ChartCard>
      </div>
    </template>

    <!-- ============================================================
         岗位推荐
    ============================================================ -->
    <template v-if="currentPage === 'recommend'">
      <div class="hero">
        <div class="hero-title">岗位推荐</div>
        <div class="hero-sub">基于技能画像智能匹配，为你推荐最合适的岗位</div>
      </div>
      <div class="chart-row chart-span">
        <ChartCard title="智能推荐结果">
          <div class="empty-state">
            输入技能标签，系统将为你匹配最佳岗位<br/>
            <span class="empty-hint">此功能开发中，敬请期待</span>
          </div>
        </ChartCard>
      </div>
    </template>

    <!-- ============================================================
         数据管理
    ============================================================ -->
    <template v-if="currentPage === 'data'">
      <div class="hero">
        <div class="hero-title">数据管理</div>
        <div class="hero-sub">爬虫任务管理与数据导入导出</div>
      </div>
      <div class="metrics">
        <MetricCard icon="◉" :value="metrics.totalJobs" label="数据总量" />
        <MetricCard icon="◎" :value="3048" label="清洗后数据" />
        <MetricCard icon="◇" :value="2" label="运行中爬虫" />
        <MetricCard icon="△" :value="20000" label="目标总量" />
      </div>
    </template>

    <!-- ============================================================
         AI 智能报告
    ============================================================ -->
    <template v-if="currentPage === 'ai'">
      <div class="hero">
        <div class="hero-title">AI 智能报告</div>
        <div class="hero-sub">DeepSeek AI 驱动的招聘市场智能分析报告</div>
      </div>
      <div class="chart-row chart-span">
        <ChartCard title="生成分析报告">
          <div class="empty-state">
            点击下方按钮，AI 将基于最新招聘数据生成深度分析报告<br/>
            <button class="btn-generate">生成报告</button>
          </div>
        </ChartCard>
      </div>
    </template>

<!-- ============================================================
         职位搜索
    ============================================================ -->
    <template v-if="currentPage === 'search'">
      <div class="hero">
        <div class="hero-title">职位搜索</div>
        <div class="hero-sub">搜索筛选 22,588 条真实职位数据，支持多维度精准过滤</div>
      </div>

      <!-- 搜索筛选栏 -->
      <div class="search-bar">
        <!-- 关键词输入框 -->
        <div class="search-input-wrap">
          <span class="search-icon">🔍</span>
          <input
            v-model="searchKeyword"
            type="text"
            class="search-input"
            placeholder="搜索职位、公司、技能..."
          />
        </div>

        <!-- 城市下拉 -->
        <select v-model="searchCity" class="search-select">
          <option value="">全部城市</option>
          <option v-for="c in allCities" :key="c" :value="c">{{ c }}</option>
        </select>

        <!-- 经验下拉 -->
        <select v-model="searchExp" class="search-select">
          <option value="">全部经验</option>
          <option v-for="e in expOptions" :key="e" :value="e">{{ e }}</option>
        </select>

        <!-- 最低薪资输入 -->
        <div class="salary-filter">
          <span class="salary-label">最低薪资</span>
          <input
            v-model.number="searchSalaryMin"
            type="number"
            class="search-salary"
            placeholder="0K"
            min="0"
            step="1"
          />
          <span class="salary-unit">K</span>
        </div>

        <!-- 结果计数 -->
        <span class="search-count">{{ filteredJobs().length }} 条结果</span>
      </div>

      <!-- 筛选结果表格 -->
      <div class="chart-row chart-span">
        <ChartCard :title="'职位列表（共 ' + filteredJobs().length + ' 条）'">
          <div v-if="filteredJobs().length === 0" class="empty-state">
            没有匹配的职位，请调整筛选条件
          </div>
          <div v-else class="job-table-wrap">
            <table class="job-table">
              <thead>
                <tr>
                  <th>职位名称</th>
                  <th>公司</th>
                  <th>城市</th>
                  <th>月薪范围</th>
                  <th>经验要求</th>
                  <th>技能标签</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in filteredJobs()" :key="job.id" class="job-row">
                  <td class="job-title">{{ job.title }}</td>
                  <td class="job-company">{{ job.company }}</td>
                  <td><span class="tag-city">{{ job.city }}</span></td>
                  <td class="job-salary">{{ job.salary_min }}K - {{ job.salary_max }}K</td>
                  <td class="job-exp">{{ job.experience }}</td>
                  <td>
                    <span v-for="sk in job.skills" :key="sk" class="tag-skill">{{ sk }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </ChartCard>
      </div>
    </template>

  </main>
</template>

<!-- ============================================================
     STYLE — 仅保留 App 级布局样式，卡片/图表样式已移入组件
============================================================ -->
<style scoped>
/* ========== 侧边栏 ========== */
.sidebar {
  width: 240px; min-width: 240px;
  background: var(--bg-sidebar, #F5F6F8);
  border-right: 1px solid var(--border, #F0F0F0);
  padding: 24px 0;
  display: flex; flex-direction: column;
  position: sticky; top: 0; height: 100vh;
}
.brand { padding: 0 16px 20px 16px; margin-bottom: 8px; }
.brand .name { font-size: 17px; font-weight: 600; letter-spacing: 0.02em; color: var(--text-1, #2C2C2C); }
.brand .sub  { font-size: 12px; color: var(--text-3, #A0A0A0); margin-top: 4px; }

.db-badge {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 18px; margin: 0 12px 20px 12px;
  background: var(--bg-card, #FFFFFF); border-radius: var(--radius-sm, 12px);
  box-shadow: var(--shadow, 0 1px 3px rgba(0,0,0,0.04));
  font-size: 12px;
}
.db-badge .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green, #7EB8A0); }
.db-label { color: var(--text-3, #A0A0A0); }
.db-value { color: var(--text-1, #2C2C2C); font-weight: 500; margin-left: auto; }

.nav-label {
  font-size: 11px; color: var(--text-3, #A0A0A0);
  padding: 0 18px; margin: 0 0 4px 0;
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 500;
}
.nav-item {
  padding: 8px 16px; margin: 2px 8px; border-radius: 12px;
  font-size: 14px; color: var(--text-2, #6B6B6B);
  cursor: pointer; transition: background 0.25s; user-select: none;
}
.nav-item:hover   { background: rgba(91,141,239,0.06); }
.nav-item.active  { background: var(--primary-soft, #EEF2FB); color: var(--primary, #5B8DEF); font-weight: 500; }

.nav-spacer { height: 24px; }

.sys-info { font-size: 12px; color: var(--text-3, #A0A0A0); padding: 0 18px; line-height: 2.2; margin-top: auto; }
.sys-row  { display: flex; justify-content: space-between; }
.sys-row span:last-child { color: var(--text-2, #6B6B6B); }

.btn-refresh {
  margin: 12px; padding: 8px 16px; border-radius: 12px; border: none;
  background: var(--primary, #5B8DEF); color: #FFF; font-weight: 500;
  font-size: 14px; cursor: pointer; transition: filter 0.3s;
}
.btn-refresh:hover { filter: brightness(0.96); }
.version { padding: 0 18px; font-size: 10px; color: var(--text-3, #A0A0A0); }

/* ========== 主内容区 ========== */
.main {
  flex: 1; padding: 2rem 3rem 3rem 3rem; max-width: 1200px;
}
.hero {
  margin-bottom: 36px; padding-bottom: 24px;
  border-bottom: 1px solid var(--border, #F0F0F0);
}
.hero-title { font-size: 1.5rem; font-weight: 600; margin-bottom: 6px; letter-spacing: -0.01em; color: var(--text-1, #2C2C2C); }
.hero-sub   { font-size: 0.88rem; color: var(--text-3, #A0A0A0); }

/* ========== 指标卡片网格（4 列） ========== */
.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

/* ========== 图表网格（2 列） ========== */
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
/* 全宽模式：图表独占一行 */
.chart-row.chart-span {
  grid-template-columns: 1fr;
}

/* 图表容器（ECharts 需要显式宽高） */
.chart-container {
  width: 100%;
}

/* ========== 词云区域 ========== */
.wordcloud {
  display: flex; flex-wrap: wrap; gap: 12px;
  align-items: center; justify-content: center;
  min-height: 300px; padding: 20px;
}

/* ========== 空状态占位 ========== */
.empty-state {
  text-align: center; color: var(--text-3, #A0A0A0);
  padding: 80px 0; font-size: 15px;
}
.empty-hint {
  font-size: 13px; margin-top: 8px; display: inline-block;
}
.btn-generate {
  margin-top: 16px; padding: 10px 24px; border-radius: 12px;
  border: none; background: var(--primary, #5B8DEF);
  color: #FFF; font-size: 14px; cursor: pointer;
}

/* ========== 搜索页面 ========== */
.search-bar {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 24px; flex-wrap: wrap;
}

/* 搜索输入框 */
.search-input-wrap {
  position: relative; flex: 1; min-width: 200px;
}
.search-icon {
  position: absolute; left: 12px; top: 50%;
  transform: translateY(-50%); font-size: 14px;
}
.search-input {
  width: 100%; padding: 10px 14px 10px 36px;
  border: 1px solid var(--border, #F0F0F0);
  border-radius: var(--radius-sm, 12px);
  background: var(--bg-card, #FFFFFF);
  font-size: 14px; color: var(--text-1, #2C2C2C);
  outline: none; transition: border-color 0.2s;
}
.search-input:focus {
  border-color: var(--primary, #5B8DEF);
}
.search-input::placeholder { color: var(--text-3, #A0A0A0); }

/* 下拉框 */
.search-select {
  padding: 10px 12px;
  border: 1px solid var(--border, #F0F0F0);
  border-radius: var(--radius-sm, 12px);
  background: var(--bg-card, #FFFFFF);
  font-size: 14px; color: var(--text-1, #2C2C2C);
  outline: none; cursor: pointer;
  min-width: 110px;
}

/* 薪资筛选 */
.salary-filter {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--border, #F0F0F0);
  border-radius: var(--radius-sm, 12px);
  background: var(--bg-card, #FFFFFF);
}
.salary-label { font-size: 12px; color: var(--text-3, #A0A0A0); white-space: nowrap; }
.salary-unit  { font-size: 13px; color: var(--text-2, #6B6B6B); }
.search-salary {
  width: 50px; border: none; outline: none;
  font-size: 14px; color: var(--text-1, #2C2C2C);
  background: transparent; text-align: right;
}

/* 结果计数 */
.search-count {
  font-size: 13px; color: var(--text-3, #A0A0A0);
  white-space: nowrap; margin-left: auto;
}

/* 职位表格 */
.job-table-wrap {
  width: 100%; overflow-x: auto;
}
.job-table {
  width: 100%; border-collapse: collapse; font-size: 14px;
}
.job-table thead {
  border-bottom: 2px solid var(--border, #F0F0F0);
}
.job-table th {
  text-align: left; padding: 12px 8px;
  font-size: 12px; font-weight: 500;
  color: var(--text-3, #A0A0A0);
  text-transform: uppercase; letter-spacing: 0.04em;
  white-space: nowrap;
}
.job-table td {
  padding: 14px 8px;
  border-bottom: 1px solid var(--border, #F0F0F0);
  color: var(--text-1, #2C2C2C);
}

.job-row { transition: background 0.15s; }
.job-row:hover { background: var(--primary-soft, #EEF2FB); }

.job-title   { font-weight: 500; }
.job-company { color: var(--text-2, #6B6B6B); }
.job-salary  { font-weight: 500; color: var(--primary, #5B8DEF); white-space: nowrap; }
.job-exp     { color: var(--text-2, #6B6B6B); white-space: nowrap; }

/* 标签 */
.tag-city  {
  display: inline-block; padding: 2px 8px;
  border-radius: 6px; font-size: 12px;
  background: var(--primary-soft, #EEF2FB);
  color: var(--primary, #5B8DEF);
}
.tag-skill {
  display: inline-block; padding: 2px 8px; margin: 1px 4px 1px 0;
  border-radius: 6px; font-size: 12px;
  background: var(--green-soft, #EEF5F1);
  color: var(--green, #7EB8A0);
}

/* ========== 响应式（768px 以下） ========== */
@media (max-width: 768px) {
  /* 侧边栏变顶部导航 */
  .sidebar {
    width: 100%; min-width: unset; height: auto;
    position: static; flex-direction: row; flex-wrap: wrap;
    padding: 12px; gap: 8px; align-items: center;
  }
  .brand { padding: 0; margin: 0; }
  .db-badge, .nav-label, .nav-spacer, .sys-info, .btn-refresh, .version { display: none; }
  .nav-item { font-size: 12px; padding: 6px 10px; margin: 0; }

  /* 主内容缩进 */
  .main { padding: 1rem; }

  /* 搜索栏纵向排列 */
  .search-bar { flex-direction: column; align-items: stretch; }
  .search-input-wrap { min-width: unset; }
  .search-select { min-width: unset; }
  .search-count { margin-left: 0; text-align: center; }
}
@media (max-width: 768px) {
  /* 侧边栏变顶部导航 */
  .sidebar {
    width: 100%; min-width: unset; height: auto;
    position: static; flex-direction: row; flex-wrap: wrap;
    padding: 12px; gap: 8px; align-items: center;
  }
  .brand { padding: 0; margin: 0; }
  .db-badge, .nav-label, .nav-spacer, .sys-info, .btn-refresh, .version { display: none; }
  .nav-item { font-size: 12px; padding: 6px 10px; margin: 0; }

  /* 主内容缩进 */
  .main { padding: 1rem; }

  /* 指标和图表都变单列 */
  .metrics, .chart-row {
    grid-template-columns: 1fr;
  }

  /* 图表容器高度自适应 */
  .chart-container { height: 260px !important; }
}
</style>
