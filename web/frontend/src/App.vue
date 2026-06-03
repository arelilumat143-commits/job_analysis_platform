<script setup>
// ============================================================
// 首页概览 — 莫兰迪极简仪表盘（和 app.py 一致的设计系统）
// 模拟数据，修改 CSS/HTML 即时生效（Vite HMR）
// ============================================================
import { ref, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'

// ---- 莫兰迪配色 ----
const C = {
  primary:       '#5B8DEF',
  primaryLight:  '#8BABF0',
  primarySoft:   '#EEF2FB',
  primarySubtle: '#F6F8FD',
  green:         '#7EB8A0',
  greenSoft:     '#EEF5F1',
  red:           '#C48B8B',
  redSoft:       '#FBF3F3',
  orange:        '#C9A87C',
  purple:        '#9B8EC4',
  bgPage:        '#FAFAFA',
  bgCard:        '#FFFFFF',
  bgSidebar:     '#F5F6F8',
  text1:         '#2C2C2C',
  text2:         '#6B6B6B',
  text3:         '#A0A0A0',
  border:        '#F0F0F0',
  shadow:        '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)',
  shadowHover:   '0 2px 8px rgba(0,0,0,0.06)',
  radius:        16,
  radiusSm:      10,
  chartColors:   ['#5B8DEF','#7EB8A0','#9B8EC4','#C9A87C','#8BABF0','#A8D0C0','#B8AED8','#D4BC9A'],
  chartBlues:    ['#EEF2FB','#D4E0F8','#A8C2F2','#7BA6EC','#5B8DEF'],
  chartGreens:   ['#EDF5F1','#D4EBE2','#A8D8C4','#7EC5A6','#5EB28E'],
}

// ---- 当前页面 ----
const currentPage = ref('overview')

// ---- 模拟数据 ----
const metrics = { totalJobs: 3048, avgSalary: '18.5 K', topCity: '成都', topSkill: 'Python' }
const cityData   = [['北京',3200],['成都',2800],['上海',2200],['深圳',1900],['杭州',1600],['武汉',1400],['广州',1200],['南京',950],['西安',820],['郑州',700]]
const sourceData = [{name:'智联招聘',value:2800},{name:'BOSS直聘',value:180},{name:'拉勾',value:50},{name:'其他',value:18}]
const industryData = [['互联网',2100],['人工智能',650],['金融',420],['电商',380],['教育',280],['医疗',200],['游戏',170],['制造业',130]]

// ---- 首次加载 + 切换页面时绘制图表 ----
function drawAllCharts() {
  nextTick(() => {
    drawCityChart()
    drawSalaryHist()
    drawSourcePie()
    drawIndustryChart()
  })
}

onMounted(() => {
  drawAllCharts()
})

// 切换到首页概览时重新绘制图表（v-if 会销毁/重建 DOM，需要重新 init）
watch(currentPage, (page) => {
  if (page === 'overview') drawAllCharts()
})

function drawCityChart() {
  const el = document.getElementById('chart-cities')
  if (!el) return
  const c = echarts.init(el)
  c.setOption({
    tooltip: { trigger:'axis' },
    grid: { left:50, right:10, top:10, bottom:20 },
    xAxis: { type:'value', axisLabel:{color:C.text3,fontSize:11}, splitLine:{lineStyle:{color:'#F5F5F5'}} },
    yAxis: { type:'category', data: cityData.map(d=>d[0]).reverse(), inverse:true, axisLabel:{color:C.text1,fontSize:12} },
    series: [{ type:'bar', data: cityData.map(d=>d[1]).reverse(), barWidth:16,
      itemStyle:{ borderRadius:[0,4,4,0], color: new echarts.graphic.LinearGradient(0,0,1,0,[
        {offset:0,color:C.chartBlues[0]},{offset:1,color:C.chartBlues[4]}
      ])}}]
  })
  window.addEventListener('resize', ()=>c.resize())
}

function drawSalaryHist() {
  const el = document.getElementById('chart-salary')
  if (!el) return
  const c = echarts.init(el)
  c.setOption({
    tooltip: { trigger:'axis' },
    grid: { left:40, right:10, top:20, bottom:20 },
    xAxis: { type:'category', data: ['0-5','5-10','10-15','15-20','20-25','25-30','30-35','35-40','40+'], axisLabel:{color:C.text3,fontSize:11} },
    yAxis: { type:'value', axisLabel:{color:C.text3,fontSize:11}, splitLine:{lineStyle:{color:'#F5F5F5'}} },
    series: [{ type:'bar', data:[2,5,8,12,7,4,1,1,0], barWidth:'60%', itemStyle:{color:C.primary,borderRadius:[4,4,0,0],opacity:0.85} }]
  })
  window.addEventListener('resize', ()=>c.resize())
}

function drawSourcePie() {
  const el = document.getElementById('chart-source')
  if (!el) return
  const c = echarts.init(el)
  c.setOption({
    tooltip: { trigger:'item' },
    series: [{ type:'pie', radius:['50%','80%'], center:['50%','55%'], itemStyle:{borderRadius:6,borderColor:'#fff',borderWidth:3}, label:{color:C.text2,fontSize:12},
      data: sourceData.map((d,i)=>({value:d.value,name:d.name,itemStyle:{color:C.chartColors[i]}})) }]
  })
  window.addEventListener('resize', ()=>c.resize())
}

function drawIndustryChart() {
  const el = document.getElementById('chart-industry')
  if (!el) return
  const c = echarts.init(el)
  c.setOption({
    tooltip: { trigger:'axis' },
    grid: { left:70, right:10, top:10, bottom:20 },
    xAxis: { type:'value', axisLabel:{color:C.text3,fontSize:11} },
    yAxis: { type:'category', data: industryData.map(d=>d[0]).reverse(), inverse:true, axisLabel:{color:C.text1,fontSize:12} },
    series: [{ type:'bar', data: industryData.map(d=>d[1]).reverse(), barWidth:16,
      itemStyle:{ borderRadius:[0,4,4,0], color: new echarts.graphic.LinearGradient(0,0,1,0,[
        {offset:0,color:C.chartGreens[1]},{offset:1,color:C.chartGreens[4]}
      ])}}]
  })
  window.addEventListener('resize', ()=>c.resize())
}
</script>

<template>
  <!-- ========== 侧边栏 ========== -->
  <aside class="sidebar">
    <div class="brand">
      <div class="name">招聘分析平台</div>
      <div class="sub">Job Analytics</div>
    </div>
    <div class="db-badge">
      <span class="dot"></span>
      <span style="color:#A0A0A0">数据库</span>
      <span style="color:#2C2C2C;font-weight:500;margin-left:auto">MYSQL</span>
    </div>
    <div class="nav-label">导航</div>
    <div class="nav-item" :class="{ active: currentPage === 'overview' }" @click="currentPage = 'overview'">◉  首页概览</div>
    <div class="nav-item" :class="{ active: currentPage === 'salary' }" @click="currentPage = 'salary'">◇  薪资分析</div>
    <div class="nav-item" :class="{ active: currentPage === 'skills' }" @click="currentPage = 'skills'">○  技能分析</div>
    <div class="nav-item" :class="{ active: currentPage === 'recommend' }" @click="currentPage = 'recommend'">□  岗位推荐</div>
    <div class="nav-item" :class="{ active: currentPage === 'data' }" @click="currentPage = 'data'">△  数据管理</div>
    <div class="nav-item" :class="{ active: currentPage === 'ai' }" @click="currentPage = 'ai'">▽  AI智能报告</div>
    <div style="height:24px"></div>
    <div class="nav-label">系统</div>
    <div class="sys-info">
      <div class="row"><span>项目</span><span>analysis_platform</span></div>
      <div class="row"><span>数据库</span><span>job_analysis</span></div>
    </div>
    <button class="btn-refresh">刷新数据缓存</button>
    <div class="version">v2.0 · Morandi Edition</div>
  </aside>

  <!-- ========== 主内容 ========== -->
  <main class="main">
    <!-- ========== 首页概览 ========== -->
    <template v-if="currentPage === 'overview'">
      <div class="hero">
        <div class="hero-title">首页概览</div>
        <div class="hero-sub">平台数据总览与核心指标一览，实时掌握招聘市场动态</div>
      </div>
      <div class="metrics">
        <div class="m-card">
          <div class="m-icon">◉</div>
          <div class="m-value">{{ metrics.totalJobs.toLocaleString() }}</div>
          <div class="m-label">总职位数</div>
        </div>
        <div class="m-card">
          <div class="m-icon">◇</div>
          <div class="m-value">{{ metrics.avgSalary }}</div>
          <div class="m-label">平均月薪</div>
        </div>
        <div class="m-card">
          <div class="m-icon">○</div>
          <div class="m-value">{{ metrics.topCity }}</div>
          <div class="m-label">热门城市</div>
        </div>
        <div class="m-card">
          <div class="m-icon">□</div>
          <div class="m-value">{{ metrics.topSkill }}</div>
          <div class="m-label">热门技能</div>
        </div>
      </div>
      <div class="chart-row">
        <div class="card">
          <h3>城市职位分布 Top 10</h3>
          <div id="chart-cities" style="width:100%;height:380px"></div>
        </div>
        <div class="card">
          <h3>薪资分布直方图</h3>
          <div id="chart-salary" style="width:100%;height:380px"></div>
        </div>
      </div>
      <div class="chart-row">
        <div class="card">
          <h3>招聘来源占比</h3>
          <div id="chart-source" style="width:100%;height:340px"></div>
        </div>
        <div class="card">
          <h3>行业分布 Top 8</h3>
          <div id="chart-industry" style="width:100%;height:340px"></div>
        </div>
      </div>
    </template>

    <!-- ========== 薪资分析 ========== -->
    <template v-if="currentPage === 'salary'">
      <div class="hero">
        <div class="hero-title">薪资分析</div>
        <div class="hero-sub">各维度薪资对比与趋势分析，洞察市场薪酬水平</div>
      </div>
      <div class="metrics">
        <div class="m-card">
          <div class="m-icon">◇</div>
          <div class="m-value">18.5K</div>
          <div class="m-label">平均月薪</div>
        </div>
        <div class="m-card">
          <div class="m-icon">◎</div>
          <div class="m-value">15.0K</div>
          <div class="m-label">薪资中位数</div>
        </div>
        <div class="m-card">
          <div class="m-icon">◉</div>
          <div class="m-value">25.5K</div>
          <div class="m-label">75分位数</div>
        </div>
        <div class="m-card">
          <div class="m-icon">△</div>
          <div class="m-value">+8.2%</div>
          <div class="m-label">同比增长</div>
        </div>
      </div>
      <div class="chart-row">
        <div class="card" style="grid-column: 1 / -1;">
          <h3>薪资分布直方图</h3>
          <div id="chart-salary-detail" style="width:100%;height:380px"></div>
        </div>
      </div>
    </template>

    <!-- ========== 技能分析 ========== -->
    <template v-if="currentPage === 'skills'">
      <div class="hero">
        <div class="hero-title">技能分析</div>
        <div class="hero-sub">热门技能需求排行与趋势变化，把握技术方向</div>
      </div>
      <div class="chart-row">
        <div class="card" style="grid-column: 1 / -1;">
          <h3>技能需求词云（模拟）</h3>
          <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:center;min-height:300px;padding:20px">
            <span style="font-size:32px;color:#5B8DEF;font-weight:600">Python</span>
            <span style="font-size:28px;color:#7EB8A0;font-weight:600">Java</span>
            <span style="font-size:26px;color:#9B8EC4;font-weight:600">SQL</span>
            <span style="font-size:24px;color:#C9A87C;font-weight:600">JavaScript</span>
            <span style="font-size:22px;color:#5B8DEF;font-weight:500">React</span>
            <span style="font-size:20px;color:#7EB8A0;font-weight:500">Linux</span>
            <span style="font-size:18px;color:#9B8EC4;font-weight:500">Docker</span>
            <span style="font-size:17px;color:#C9A87C;font-weight:500">Git</span>
            <span style="font-size:16px;color:#8BABF0;font-weight:500">K8s</span>
            <span style="font-size:15px;color:#A8D0C0;font-weight:500">AWS</span>
          </div>
        </div>
      </div>
    </template>

    <!-- ========== 岗位推荐 ========== -->
    <template v-if="currentPage === 'recommend'">
      <div class="hero">
        <div class="hero-title">岗位推荐</div>
        <div class="hero-sub">基于技能画像智能匹配，为你推荐最合适的岗位</div>
      </div>
      <div class="chart-row">
        <div class="card" style="grid-column: 1 / -1;">
          <h3>智能推荐结果</h3>
          <div style="text-align:center;color:#A0A0A0;padding:80px 0;font-size:15px">
            输入技能标签，系统将为你匹配最佳岗位<br/>
            <span style="font-size:13px;margin-top:8px;display:inline-block">此功能开发中，敬请期待</span>
          </div>
        </div>
      </div>
    </template>

    <!-- ========== 数据管理 ========== -->
    <template v-if="currentPage === 'data'">
      <div class="hero">
        <div class="hero-title">数据管理</div>
        <div class="hero-sub">爬虫任务管理与数据导入导出</div>
      </div>
      <div class="metrics">
        <div class="m-card">
          <div class="m-icon">◉</div>
          <div class="m-value">{{ metrics.totalJobs.toLocaleString() }}</div>
          <div class="m-label">数据总量</div>
        </div>
        <div class="m-card">
          <div class="m-icon">◎</div>
          <div class="m-value">3,048</div>
          <div class="m-label">清洗后数据</div>
        </div>
        <div class="m-card">
          <div class="m-icon">◇</div>
          <div class="m-value">2</div>
          <div class="m-label">运行中爬虫</div>
        </div>
        <div class="m-card">
          <div class="m-icon">△</div>
          <div class="m-value">20,000</div>
          <div class="m-label">目标总量</div>
        </div>
      </div>
    </template>

    <!-- ========== AI智能报告 ========== -->
    <template v-if="currentPage === 'ai'">
      <div class="hero">
        <div class="hero-title">AI 智能报告</div>
        <div class="hero-sub">DeepSeek AI 驱动的招聘市场智能分析报告</div>
      </div>
      <div class="chart-row">
        <div class="card" style="grid-column: 1 / -1;">
          <h3>生成分析报告</h3>
          <div style="text-align:center;color:#A0A0A0;padding:80px 0;font-size:15px">
            点击下方按钮，AI 将基于最新招聘数据生成深度分析报告<br/>
            <button style="margin-top:16px;padding:10px 24px;border-radius:12px;border:none;background:#5B8DEF;color:#FFF;font-size:14px;cursor:pointer">
              生成报告
            </button>
          </div>
        </div>
      </div>
    </template>
  </main>
</template>

<style scoped>
/* ========== 侧边栏（和 app.py 一模一样）========== */
.sidebar {
  width: 240px; min-width: 240px;
  background: #F5F6F8;
  border-right: 1px solid #F0F0F0;
  padding: 24px 0;
  display: flex; flex-direction: column;
  position: sticky; top: 0; height: 100vh;
}
.brand { padding: 0 16px 20px 16px; margin-bottom: 8px; }
.brand .name { font-size: 17px; font-weight: 600; letter-spacing: 0.02em; }
.brand .sub  { font-size: 12px; color: #A0A0A0; margin-top: 4px; }
.db-badge {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 18px; margin: 0 12px 20px 12px;
  background: #FFF; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  font-size: 12px;
}
.db-badge .dot { width: 7px; height: 7px; border-radius: 50%; background: #7EB8A0; }
.nav-label {
  font-size: 11px; color: #A0A0A0; padding: 0 18px; margin: 0 0 4px 0;
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 500;
}
.nav-item {
  padding: 8px 16px; margin: 2px 8px; border-radius: 12px;
  font-size: 14px; color: #6B6B6B; cursor: pointer;
  transition: background 0.3s; user-select: none;
}
.nav-item:hover { background: rgba(91,141,239,0.06); }
.nav-item.active { background: #EEF2FB; color: #5B8DEF; font-weight: 500; }
.sys-info { font-size: 12px; color: #A0A0A0; padding: 0 18px; line-height: 2.2; margin-top: auto; }
.sys-info .row { display: flex; justify-content: space-between; }
.sys-info .row span:last-child { color: #6B6B6B; }
.btn-refresh {
  margin: 12px; padding: 8px 16px; border-radius: 12px; border: none;
  background: #5B8DEF; color: #FFF; font-weight: 500; font-size: 14px;
  cursor: pointer; transition: filter 0.3s;
}
.btn-refresh:hover { filter: brightness(0.96); }
.version { padding: 0 18px; font-size: 10px; color: #A0A0A0; }

/* ========== 主内容 ========== */
.main {
  flex: 1; padding: 2rem 3rem 3rem 3rem; max-width: 1200px;
}
.hero {
  margin-bottom: 36px; padding-bottom: 24px;
  border-bottom: 1px solid #F0F0F0;
}
.hero-title  { font-size: 1.5rem; font-weight: 600; margin-bottom: 6px; letter-spacing: -0.01em; }
.hero-sub    { font-size: 0.88rem; color: #A0A0A0; }

/* 指标卡片 */
.metrics {
  display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 28px;
}
.m-card {
  background: #FFF; border-radius: 16px; padding: 28px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04); text-align: center;
  transition: box-shadow 0.4s;
}
.m-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.m-icon  { font-size: 1.5rem; margin-bottom: 10px; opacity: 0.7; }
.m-value { font-size: 2.2rem; font-weight: 600; line-height: 1.2; letter-spacing: -0.02em; }
.m-label { font-size: 0.82rem; color: #A0A0A0; margin-top: 6px; }

/* 图表 */
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.card {
  background: #FFF; border-radius: 16px; padding: 28px 32px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }

@media (max-width: 768px) {
  #app { flex-direction: column; }
  .sidebar { width: 100%; height: auto; position: static; }
  .main { padding: 1rem; }
  .metrics, .chart-row { grid-template-columns: 1fr; }
}
</style>
