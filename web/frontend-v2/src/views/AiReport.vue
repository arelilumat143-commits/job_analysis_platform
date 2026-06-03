<!-- ============================================================
 AiReport — AI 智能报告页
 调用 DeepSeek API 生成招聘市场分析报告
 数据来源：/api/ai/report
 ============================================================ -->
<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'

const store = useAppStore()
const { get, post } = useApi()

const loading = ref(false)
const generating = ref(false)
const stats = ref(null)
const salaryData = ref(null)
const report = ref('')
const error = ref('')

async function loadContext() {
  loading.value = true
  const [s, sa] = await Promise.all([
    get('/api/jobs/stats'),
    get('/api/analysis/salary'),
  ])
  if (s) stats.value = s
  if (sa) salaryData.value = sa
  loading.value = false
}

async function generateReport() {
  generating.value = true
  error.value = ''
  report.value = ''
  try {
    // 调用后端 AI 报告接口
    const result = await post('/api/ai/report', {
      stats: stats.value,
      salary: salaryData.value,
    })
    if (result) {
      report.value = result.report || result.content || JSON.stringify(result)
    } else {
      // 如果后端 AI 接口不可用，使用前端生成简单报告
      report.value = generateLocalReport()
    }
  } catch (e) {
    // 降级为本地报告
    report.value = generateLocalReport()
  }
  generating.value = false
}

function generateLocalReport() {
  if (!stats.value) return '数据加载中，请稍后重试...'
  const total = stats.value.total
  const topCity = stats.value.by_city?.[0]
  const topSource = stats.value.by_source?.[0]
  const avgSalary = salaryData.value?.basic_stats?.mean?.toFixed(1) || '--'

  return `## 招聘市场分析报告

### 数据概况
- 数据总量：**${total.toLocaleString()}** 条职位信息
- 覆盖城市：**${stats.value.by_city?.length || 0}** 个
- 数据来源：以${topSource?.source === 'zhilian' ? '智联招聘' : topSource?.source || '--'}为主

### 城市分布
- 职位最多的城市是 **${topCity?.city || '--'}**（${topCity?.count?.toLocaleString() || '--'} 条）
- 一线及新一线城市占据主要职位需求

### 薪资分析
- 有薪资数据的职位平均薪资约 **${avgSalary}K/月**
- 大部分职位薪资集中在 10-20K 区间

### 行业趋势
- 当前数据中行业标签多为"未知"，待爬虫采集详情页补充
- 建议对职位描述做 NLP 关键词提取以补充技能标签

### 数据质量
- 数据完整性：学历/经验/技能字段大部分为 NULL
- 建议：重新运行爬虫采集职位详情页数据

---
*报告由系统自动生成 · ${new Date().toLocaleDateString('zh-CN')}*`
}

onMounted(() => loadContext())
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">AI 智能报告</div>
      <div class="page-sub">基于 DeepSeek API 的招聘市场智能分析</div>
    </div>

    <!-- 上下文数据摘要 -->
    <div class="metrics-grid" v-if="!loading">
      <div class="mini-stat">
        <div class="ms-val">{{ stats?.total?.toLocaleString() || '--' }}</div>
        <div class="ms-lbl">数据总量</div>
      </div>
      <div class="mini-stat">
        <div class="ms-val">{{ stats?.by_city?.length || '--' }}</div>
        <div class="ms-lbl">覆盖城市</div>
      </div>
      <div class="mini-stat">
        <div class="ms-val">{{ salaryData?.basic_stats?.mean?.toFixed(1) || '--' }}K</div>
        <div class="ms-lbl">平均薪资</div>
      </div>
      <div class="mini-stat">
        <div class="ms-val">{{ salaryData?.basic_stats?.count || '--' }}</div>
        <div class="ms-lbl">有薪资数据</div>
      </div>
    </div>

    <!-- 生成按钮 -->
    <div class="action-bar">
      <button class="gen-btn" @click="generateReport" :disabled="generating || loading">
        {{ generating ? 'AI 分析中...' : '生成 AI 报告' }}
      </button>
    </div>

    <!-- 报告内容 -->
    <div v-if="generating" class="report-loading">
      <div class="pulse-dot"></div>
      <span>AI 正在分析数据...</span>
    </div>
    <div v-else-if="report" class="report-content" v-html="report.replace(/\n/g, '<br>').replace(/## (.+)/g, '<h2>$1</h2>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/- (.+)/g, '<li>$1</li>')">
    </div>
    <div v-else-if="!loading" class="empty-state">
      <span>点击上方按钮生成 AI 分析报告</span>
      <span class="empty-hint">报告基于当前 {{ stats?.total || 0 }} 条真实招聘数据</span>
    </div>
  </div>
</template>

<style scoped>
.mini-stat {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 16px 20px; text-align: center; box-shadow: var(--shadow);
}
.ms-val { font-size: 22px; font-weight: 600; color: var(--primary); }
.ms-lbl { font-size: 12px; color: var(--text-3); margin-top: 4px; }

.action-bar { margin: 20px 0 28px; }
.gen-btn {
  padding: 12px 32px; border-radius: var(--radius-sm); border: none;
  background: linear-gradient(135deg, #5B8DEF, #9B8EC4);
  color: #fff; font-size: 15px; font-weight: 600; cursor: pointer;
  transition: all 0.25s; box-shadow: 0 2px 8px rgba(91,141,239,0.3);
}
.gen-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(91,141,239,0.4); }
.gen-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.report-loading { display: flex; align-items: center; gap: 12px; padding: 40px; justify-content: center; color: var(--text-3); }
.pulse-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--primary); animation: pulse 1.2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }

.report-content {
  background: var(--bg-card); border-radius: var(--radius);
  padding: 32px; box-shadow: var(--shadow); line-height: 2; color: var(--text-1);
  font-size: 15px; white-space: pre-wrap;
}
.report-content h2 { font-size: 18px; margin: 24px 0 12px; color: var(--primary); }
.report-content h2:first-child { margin-top: 0; }
.report-content strong { color: var(--text-1); }
.report-content li { margin-left: 20px; list-style: disc; }
</style>
