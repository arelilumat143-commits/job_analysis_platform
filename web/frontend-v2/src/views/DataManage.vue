<!-- ============================================================
 DataManage — 数据管理页
 展示数据库状态、爬虫状态、最近爬取时间
 数据来源：/api/crawler/status + /api/jobs/stats
 ============================================================ -->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import MetricCard from '../components/MetricCard.vue'

const store = useAppStore()
const { get, post } = useApi()

const loading = ref(true)
const stats = ref(null)
const crawlerStatus = ref(null)
const lastUpdate = ref('--')

async function loadData() {
  loading.value = true
  const s = await get('/api/jobs/stats')
  if (s) stats.value = s
  // 尝试获取爬虫状态
  try {
    const cs = await get('/api/crawler/status')
    if (cs) crawlerStatus.value = cs
  } catch { /* 爬虫 API 可能不可用 */ }
  lastUpdate.value = new Date().toLocaleString('zh-CN')
  loading.value = false
}

// 数据质量
const dataQuality = computed(() => {
  if (!stats.value) return { score: 0, label: '--' }
  const total = stats.value.total
  // 简单评分：有数据就给基础分
  if (total > 20000) return { score: 85, label: '良好' }
  if (total > 10000) return { score: 70, label: '一般' }
  return { score: 50, label: '待补充' }
})

onMounted(() => loadData())
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">数据管理</div>
      <div class="page-sub">数据库状态与爬虫监控 · 最后更新：{{ lastUpdate }}</div>
    </div>

    <!-- 指标卡片 -->
    <div class="metrics-grid">
      <MetricCard icon="◉" :value="stats?.total || 0" label="数据库总记录" :loading="loading" />
      <MetricCard icon="◇" :value="stats?.by_city?.length || 0" label="覆盖城市数" :loading="loading" />
      <MetricCard icon="△" :value="dataQuality.score" label="数据质量评分" :loading="loading" />
      <MetricCard icon="▽" :value="dataQuality.label" label="数据质量等级" :loading="loading" />
    </div>

    <!-- 数据详情 -->
    <div class="section" v-if="!loading">
      <h3 class="section-title">城市数据分布</h3>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>城市</th><th>职位数</th><th>占比</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in stats?.by_city || []" :key="c.city">
              <td>{{ c.city }}</td>
              <td>{{ c.count.toLocaleString() }}</td>
              <td>
                <div class="pct-bar">
                  <div class="pct-fill" :style="{ width: (c.count / stats.total * 100).toFixed(1) + '%' }"></div>
                  <span>{{ (c.count / stats.total * 100).toFixed(1) }}%</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 数据来源 -->
    <div class="section" v-if="!loading && stats?.by_source">
      <h3 class="section-title">数据来源分布</h3>
      <div class="source-cards">
        <div class="source-card" v-for="s in stats.by_source" :key="s.source">
          <div class="sc-name">{{ s.source === 'zhilian' ? '智联招聘' : s.source === 'boss' ? 'BOSS直聘' : '拉勾网' }}</div>
          <div class="sc-count">{{ s.count.toLocaleString() }} 条</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section { margin-top: 28px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--text-2); }

.data-table-wrap { background: var(--bg-card); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; }
.data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.data-table th { text-align: left; padding: 12px 20px; background: var(--bg-sidebar); color: var(--text-2); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
.data-table td { padding: 12px 20px; border-top: 1px solid var(--border); color: var(--text-1); }

.pct-bar { display: flex; align-items: center; gap: 8px; }
.pct-fill { height: 6px; border-radius: 3px; background: var(--primary); min-width: 2px; transition: width 0.5s; }

.source-cards { display: flex; gap: 16px; }
.source-card {
  flex: 1; background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px; box-shadow: var(--shadow); text-align: center;
}
.sc-name  { font-size: 14px; color: var(--text-2); margin-bottom: 6px; }
.sc-count { font-size: 22px; font-weight: 600; color: var(--primary); }
</style>
