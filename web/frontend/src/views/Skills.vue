<!-- ============================================================
 Skills v2 — 技能分析页（增强版）
 新增：技能学习路线图 / 分类统计 / 技能云
 数据来源：/api/analysis/skill
 ============================================================ -->
<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import { useChart } from '../composables/useChart.js'
import ChartCard from '../components/ChartCard.vue'
import * as echarts from 'echarts'

const store = useAppStore()
const { get } = useApi()
const { init: initChart, setOption: setChart, readCssVar } = useChart()

const loading = ref(true)
const skillsData = ref(null)
const errorMsg = ref('')

// ---- 技能分类规则 ----
const categoryRules = [
  { cat: '后端', keywords: ['java', 'spring', 'django', 'go', 'golang', 'rust', 'node', 'express', 'gin', 'fastapi', 'flask', 'mybatis', 'hibernate', 'nestjs', 'koa'] },
  { cat: '前端', keywords: ['javascript', 'typescript', 'react', 'vue', 'angular', 'css', 'html', 'webpack', 'vite', 'jquery', 'sass', 'less'] },
  { cat: '数据', keywords: ['sql', 'mysql', 'redis', 'mongodb', 'postgres', 'oracle', 'hadoop', 'spark', 'flink', 'etl', 'clickhouse', 'elasticsearch', 'kafka'] },
  { cat: '运维', keywords: ['linux', 'docker', 'kubernetes', 'jenkins', 'ansible', 'nginx', 'tomcat', 'shell', 'gitlab', 'terraform'] },
  { cat: '云服务', keywords: ['aws', 'azure', 'gcp', 'aliyun', 'cloud', 'serverless'] },
  { cat: 'AI', keywords: ['python', 'pytorch', 'tensorflow', 'nlp', '算法', '机器学习', '深度学习', 'cv', 'transformer', 'llm'] },
]

function classifySkill(name) {
  const lower = name.toLowerCase()
  for (const rule of categoryRules) {
    if (rule.keywords.some(k => lower.includes(k))) return rule.cat
  }
  return '其他'
}

// ---- 学习路线图（静态知识库）----
const learningRoadmap = [
  {
    title: '后端开发', icon: 'BE',
    levels: [
      { stage: '初级', skills: '一门语言(Python/Java/Go) + SQL基础 + Git' },
      { stage: '中级', skills: 'Web框架 + 数据库设计 + RESTful API + 缓存(Redis)' },
      { stage: '高级', skills: '微服务架构 + 消息队列 + 性能调优 + 系统设计' },
    ]
  },
  {
    title: '前端开发', icon: 'FE',
    levels: [
      { stage: '初级', skills: 'HTML/CSS/JavaScript + Vue或React入门' },
      { stage: '中级', skills: 'TypeScript + 状态管理 + 工程化(Webpack/Vite)' },
      { stage: '高级', skills: '架构设计 + 性能优化 + SSR/SSG + 跨端方案' },
    ]
  },
  {
    title: '数据工程', icon: 'DE',
    levels: [
      { stage: '初级', skills: 'SQL精通 + Python + 数据清洗' },
      { stage: '中级', skills: 'Spark/Hadoop + 数据管道 + 数据仓库设计' },
      { stage: '高级', skills: '实时计算 + 数据治理 + 架构设计 + MLOps' },
    ]
  },
  {
    title: 'AI/ML', icon: 'AI',
    levels: [
      { stage: '初级', skills: 'Python + 数学基础 + sklearn入门' },
      { stage: '中级', skills: '深度学习框架 + 模型调优 + 特征工程' },
      { stage: '高级', skills: '大模型微调 + 模型部署 + 论文复现 + 系统设计' },
    ]
  },
]

// ---- 分类统计 ----
const categoryStats = computed(() => {
  if (!skillsData.value?.top_skills?.length) return []
  const catMap = {}
  skillsData.value.top_skills.forEach(s => {
    const cat = classifySkill(s.skill)
    catMap[cat] = (catMap[cat] || 0) + s.count
  })
  return Object.entries(catMap).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)
})

// ---- 数据加载 ----
async function loadData() {
  loading.value = true
  errorMsg.value = ''
  const data = await get('/api/analysis/skill', { limit: 50 })
  if (data?.top_skills) skillsData.value = data
  else errorMsg.value = '技能数据加载失败，请检查后端服务'
  loading.value = false
}

// ---- 图表渲染 ----
function renderSkillsBar() {
  const c = initChart('chart-skills-bar')
  if (!c) return
  if (!skillsData.value?.top_skills?.length) {
    setChart('chart-skills-bar', {
      title: { text: '暂无技能数据', subtext: '需要先运行详情页爬虫采集技能字段', left: 'center', top: 'center',
        textStyle: { color: readCssVar('--text-3'), fontSize: 15 },
        subtextStyle: { color: readCssVar('--text-3'), fontSize: 12 }},
      backgroundColor: 'transparent',
    })
    return
  }
  const top15 = skillsData.value.top_skills.slice(0, 15)
  setChart('chart-skills-bar', {
    tooltip: { trigger: 'axis' },
    grid: { left: 90, right: 50, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: '职位数' },
    yAxis: {
      type: 'category', data: top15.map(x => x.skill).reverse(),
      axisLabel: { color: readCssVar('--text-2'), fontSize: 11 },
    },
    series: [{
      type: 'bar', data: top15.map(x => x.count).reverse(),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: readCssVar('--primary') }, { offset: 1, color: readCssVar('--primary-light') }
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
  if (!categoryStats.value.length) {
    setChart('chart-skills-pie', {
      title: { text: '暂无分类数据', left: 'center', top: 'center',
        textStyle: { color: readCssVar('--text-3'), fontSize: 14 }},
      backgroundColor: 'transparent',
    })
    return
  }
  setChart('chart-skills-pie', {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: readCssVar('--text-2'), fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['40%', '68%'], center: ['50%', '45%'],
      data: categoryStats.value, label: { show: false },
      emphasis: { label: { show: true, fontWeight: 'bold' } },
      itemStyle: { borderRadius: 3, borderColor: 'transparent', borderWidth: 2 },
    }],
    color: [readCssVar('--primary'), readCssVar('--green'), readCssVar('--orange'), readCssVar('--purple'), readCssVar('--red'), readCssVar('--orange-light'), readCssVar('--green-light')],
    backgroundColor: 'transparent',
  })
}

function renderAllCharts() {
  renderSkillsBar()
  renderSkillsPie()
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
      <div class="page-title">技能分析</div>
      <div class="page-sub">热门技能需求分布 · 共 {{ skillsData?.top_skills?.length || 0 }} 项技能 · 数据来自职位详情页</div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-banner">{{ errorMsg }}</div>

    <!-- 图表区 -->
    <div class="chart-grid">
      <ChartCard title="热门技能 TOP15" :loading="loading">
        <div id="chart-skills-bar" style="width:100%;height:380px"></div>
      </ChartCard>
      <ChartCard title="技能类别分布" :loading="loading">
        <div id="chart-skills-pie" style="width:100%;height:380px"></div>
      </ChartCard>
    </div>

    <!-- 技能云 + 分类统计 -->
    <div class="skill-cloud" v-if="!loading && skillsData?.top_skills?.length">
      <div class="skill-tag" v-for="s in skillsData.top_skills.slice(0, 30)" :key="s.skill"
        :style="{ fontSize: (12 + s.count / Math.max(1, skillsData.top_skills[0].count) * 18) + 'px', opacity: 0.5 + (s.count / Math.max(1, skillsData.top_skills[0].count)) * 0.5 }">
        {{ s.skill }}
        <span class="tag-count">{{ s.count }}</span>
      </div>
    </div>

    <!-- 技能学习路线图 -->
    <div class="roadmap-section">
      <h3 class="section-title">技能成长路线参考</h3>
      <div class="roadmap-grid">
        <div class="roadmap-card" v-for="track in learningRoadmap" :key="track.title">
          <div class="rm-header">
            <span class="rm-icon">{{ track.icon }}</span>
            <span class="rm-title">{{ track.title }}</span>
          </div>
          <div class="rm-levels">
            <div class="rm-level" v-for="lv in track.levels" :key="lv.stage">
              <div class="rm-stage">{{ lv.stage }}</div>
              <div class="rm-skills">{{ lv.skills }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空数据引导 -->
    <div class="empty-guide" v-if="!loading && !skillsData?.top_skills?.length && !errorMsg">
      <div class="eg-icon">!</div>
      <div class="eg-title">技能数据待采集</div>
      <div class="eg-desc">
        当前技能字段为空，需要运行"详情页数据补充"爬虫来采集职位的技能、经验、学历等详细信息。<br>
        前往 <strong>数据管理</strong> 页面，选择目标城市，点击"抓取详情页"按钮。
      </div>
    </div>
  </div>
</template>

<style scoped>
.error-banner {
  padding: 12px 20px; margin-bottom: 16px; border-radius: var(--radius-sm);
  background: var(--red-soft); color: var(--red); font-size: 13px;
}

.skill-cloud {
  display: flex; flex-wrap: wrap; gap: 10px; padding: 24px;
  justify-content: center; margin-bottom: 28px;
  background: var(--bg-card); border-radius: var(--radius-sm); box-shadow: var(--shadow);
}
.skill-tag {
  padding: 6px 14px; border-radius: 20px;
  background: var(--primary-soft); color: var(--primary);
  font-weight: 500; transition: all 0.2s; cursor: default;
  display: flex; align-items: center; gap: 6px;
}
.skill-tag:hover { transform: scale(1.08); box-shadow: var(--shadow-hover); }
.tag-count { font-size: 0.7em; opacity: 0.6; font-weight: 400; }

/* 学习路线图 */
.roadmap-section { margin-top: 8px; }
.section-title { font-size: 16px; font-weight: 600; color: var(--text-1); margin-bottom: 16px; }
.roadmap-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.roadmap-card {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px; box-shadow: var(--shadow); border: 1px solid var(--border);
}
.rm-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.rm-icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: var(--primary-soft); color: var(--primary);
  font-size: 12px; font-weight: 700;
}
.rm-title { font-size: 15px; font-weight: 600; color: var(--text-1); }
.rm-levels { display: flex; flex-direction: column; gap: 8px; }
.rm-level {
  display: flex; gap: 12px; padding: 8px 12px; border-radius: 6px;
  background: var(--bg-page);
}
.rm-stage {
  font-size: 11px; font-weight: 600; color: var(--primary);
  min-width: 32px; padding-top: 1px;
}
.rm-skills { font-size: 12px; color: var(--text-3); line-height: 1.6; }

/* 空数据引导 */
.empty-guide {
  text-align: center; padding: 40px 20px; margin-top: 20px;
  background: var(--bg-card); border-radius: var(--radius-sm); box-shadow: var(--shadow);
  border: 2px dashed var(--border);
}
.eg-icon {
  width: 48px; height: 48px; border-radius: 50%; margin: 0 auto 14px;
  display: flex; align-items: center; justify-content: center;
  background: var(--primary-soft); color: var(--primary);
  font-size: 22px; font-weight: 700;
}
.eg-title { font-size: 17px; font-weight: 600; color: var(--text-1); margin-bottom: 8px; }
.eg-desc { font-size: 13px; color: var(--text-3); line-height: 1.8; max-width: 500px; margin: 0 auto; }

@media (max-width: 768px) {
  .roadmap-grid { grid-template-columns: 1fr; }
}
</style>
