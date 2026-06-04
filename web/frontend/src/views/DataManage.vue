<!-- ============================================================
 DataManage — 数据管理 + 爬虫控制面板
 功能：数据库状态 / 城市分布 / 爬虫启停 / 任务监控 / 企业仪表盘
 数据来源：/api/jobs/stats + /api/crawler/*
 ============================================================ -->
<script setup>
// ============================================================
// DataManage — 数据管理 + 爬虫控制面板
// 爬虫状态/日志由 Pinia useCrawlerStore 管理，切换页面不丢失
// ============================================================
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useCrawlerStore } from '../stores/crawler.js'
import { useApi } from '../composables/useApi.js'
import MetricCard from '../components/MetricCard.vue'

const store = useAppStore()
const crawler = useCrawlerStore()
const { get } = useApi()

const loading = ref(true)
const stats = ref(null)
const crawlerStatus = ref(null)
const lastUpdate = ref('--')

// 可用数据源（仅智联已实现）
const sources = [
  { id: 'zhilian', name: '智联招聘', icon: '◉', color: '#5B8DEF' },
  { id: 'boss', name: 'BOSS直聘', icon: '◆', color: '#7EB8A0', disabled: true },
  { id: 'qiancheng', name: '前程无忧', icon: '●', color: '#C9A87C', disabled: true },
  { id: 'shixiseng', name: '实习僧', icon: '▲', color: '#9B8EC4', disabled: true },
]

const cities = ['北京','上海','广州','深圳','杭州','成都','南京','武汉','西安','郑州','合肥','天津','长沙','重庆','青岛','济南','苏州','厦门','大连']

async function loadData() {
  loading.value = true
  const s = await get('/api/jobs/stats')
  if (s) stats.value = s
  await refreshCrawlerStatus()
  lastUpdate.value = new Date().toLocaleString('zh-CN')
  loading.value = false
}

async function refreshCrawlerStatus() {
  try {
    const cs = await get('/api/crawler/status')
    if (cs) crawlerStatus.value = cs
  } catch { /* ignore */ }
}

// 数据质量评分
const dataQuality = computed(() => {
  if (!stats.value) return { score: 0, label: '--', color: 'var(--text-3)' }
  const total = stats.value.total
  if (total > 30000) return { score: 95, label: '优秀', color: 'var(--green)' }
  if (total > 20000) return { score: 85, label: '良好', color: 'var(--primary)' }
  if (total > 10000) return { score: 70, label: '一般', color: 'var(--orange)' }
  return { score: 50, label: '待补充', color: 'var(--red)' }
})

const cityDetail = computed(() => {
  if (!stats.value?.by_city) return []
  return stats.value.by_city.slice(0, 10).map(c => ({
    ...c,
    pct: (c.count / stats.value.total * 100).toFixed(1),
  }))
})

onMounted(() => {
  loadData()
  // 注册数据刷新回调（爬虫完成后自动刷新页面数据）
  crawler.onDataRefresh(() => {
    loadData()
    refreshCrawlerStatus()
  })
  // 检查是否有遗留的运行中任务，恢复轮询
  crawler.reconcileWithBackend()
})

// 组件卸载时不做任何清理 — 爬虫状态/轮询/日志都在 Store 中，
// 切换页面后继续运行，回来时通过 reconcileWithBackend 自动恢复
onUnmounted(() => {
  // 只注销回调，不停止轮询
  crawler.onDataRefresh(null)
})
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">数据管理</div>
      <div class="page-sub">数据监控与爬虫控制中心 · 最后更新：{{ lastUpdate }}</div>
    </div>

    <!-- ====== 企业仪表盘指标卡 ====== -->
    <div class="metrics-grid">
      <MetricCard icon="◉" :value="stats?.total || 0" label="数据库总记录" :loading="loading" />
      <MetricCard icon="◇" :value="stats?.by_city?.length || 0" label="覆盖城市数" :loading="loading" />
      <MetricCard icon="△" :value="dataQuality.score" :label="dataQuality.label" :loading="loading" />
      <MetricCard icon="⬡" :value="crawlerStatus?.total_collected || '--'" label="爬虫累计采集" :loading="loading" />
    </div>

    <!-- ====== 爬虫控制面板 ====== -->
    <div class="panel">
      <div class="panel-header">
        <h3 class="panel-title">爬虫控制台</h3>
        <div class="status-badge" :class="crawler.crawlRunning ? 'running' : 'idle'">
          <span class="status-dot"></span>
          {{ crawler.crawlRunning ? '运行中' : '空闲' }}
        </div>
      </div>

      <div class="crawl-body">
        <!-- 左侧：爬虫配置 -->
        <div class="crawl-config">
          <!-- 数据源选择 -->
          <div class="form-group">
            <label class="form-label">数据源</label>
            <div class="source-selector">
              <div v-for="s in sources" :key="s.id" class="source-option"
                :class="{ active: crawler.crawlForm.source === s.id, disabled: s.disabled }"
                :style="{ borderColor: crawler.crawlForm.source === s.id ? s.color : 'var(--border)' }"
                @click="!s.disabled && (crawler.crawlForm.source = s.id)">
                <span class="so-icon">{{ s.icon }}</span>
                <span class="so-name">{{ s.name }}</span>
              </div>
            </div>
          </div>

          <!-- 城市选择 -->
          <div class="form-group">
            <label class="form-label">目标城市</label>
            <select v-model="crawler.crawlForm.city" class="form-select">
              <option value="">全国（不限）</option>
              <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>

          <!-- 关键词 + 页数 -->
          <div class="form-row">
            <div class="form-group" style="flex:1">
              <label class="form-label">搜索关键词</label>
              <input v-model="crawler.crawlForm.keyword" class="form-input" placeholder="如 Java、产品经理..." />
            </div>
            <div class="form-group" style="width:130px">
              <label class="form-label">爬取页数</label>
              <select v-model="crawler.crawlForm.pages" class="form-select">
                <option :value="1">1 页</option>
                <option :value="3">3 页</option>
                <option :value="5">5 页</option>
                <option :value="10">10 页</option>
                <option :value="20">20 页</option>
              </select>
            </div>
          </div>

          <!-- 按钮 -->
          <div class="btn-row">
            <button class="btn-start" :disabled="crawler.crawlRunning" @click="crawler.startCrawl">
              {{ crawler.crawlRunning ? '运行中...' : '启动爬虫' }}
            </button>
            <button class="btn-stop" :disabled="!crawler.crawlRunning" @click="crawler.stopCrawl">
              停止
            </button>
          </div>
        </div>

        <!-- 右侧：实时日志 -->
        <div class="crawl-log">
          <div class="log-header">实时日志</div>
          <div class="log-body" ref="logBody">
            <div v-if="!crawler.crawlLogs.length" class="log-empty">等待爬虫启动...</div>
            <div v-for="(log, i) in crawler.crawlLogs" :key="i" class="log-line" :class="'log-' + log.type">
              <span class="log-time">{{ log.time }}</span>
              <span class="log-msg">{{ log.msg }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 详情页爬取面板 ====== -->
    <div class="panel" style="margin-top:16px">
      <div class="panel-header">
        <h3 class="panel-title">详情页数据补充</h3>
        <div class="status-badge" :class="crawler.detailRunning ? 'running' : 'idle'">
          <span class="status-dot"></span>
          {{ crawler.detailRunning ? '抓取中' : '空闲' }}
        </div>
      </div>
      <div class="crawl-body" style="min-height:auto">
        <div class="crawl-config" style="width:280px">
          <div class="form-group">
            <label class="form-label">目标城市</label>
            <select v-model="crawler.detailForm.city" class="form-select">
              <option value="">全部城市</option>
              <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div class="form-row">
            <div class="form-group" style="flex:1">
              <label class="form-label">每次数量</label>
              <select v-model="crawler.detailForm.limit" class="form-select">
                <option :value="20">20 条</option>
                <option :value="50">50 条</option>
                <option :value="100">100 条</option>
                <option :value="200">200 条</option>
                <option :value="500">500 条</option>
              </select>
            </div>
          </div>
          <div class="btn-row">
            <button class="btn-start" :disabled="crawler.detailRunning" @click="crawler.startDetailScrape">
              {{ crawler.detailRunning ? '抓取中...' : '抓取详情页' }}
            </button>
            <button class="btn-stop" :disabled="!crawler.detailRunning" @click="crawler.stopDetailScrape">停止</button>
          </div>
        </div>
        <div class="crawl-log">
          <div class="log-header">详情抓取进度</div>
          <div class="log-body" style="max-height:140px">
            <div v-if="crawler.detailStats.total === 0 && !crawler.detailRunning" class="log-empty">
              点击"抓取详情页"补充职位经验/学历/技能/行业等字段
            </div>
            <div v-else class="detail-stats">
              <div class="ds-row">
                <span>总数</span><span class="dsv">{{ crawler.detailStats.total || '--' }}</span>
              </div>
              <div class="ds-row">
                <span>请求成功</span><span class="dsv" style="color:var(--green)">{{ crawler.detailStats.success || 0 }}</span>
              </div>
              <div class="ds-row">
                <span>字段已更新</span><span class="dsv" style="color:var(--primary)">{{ crawler.detailStats.updated || 0 }}</span>
              </div>
              <div class="ds-row">
                <span>失败</span><span class="dsv" style="color:var(--red)">{{ crawler.detailStats.failed || 0 }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 城市数据分布表 ====== -->
    <div class="section" v-if="!loading">
      <h3 class="section-title">城市数据分布</h3>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>#</th><th>城市</th><th>职位数</th><th>占比</th></tr>
          </thead>
          <tbody>
            <tr v-for="(c, i) in cityDetail" :key="c.city">
              <td class="td-rank">{{ i + 1 }}</td>
              <td>{{ c.city }}</td>
              <td class="td-num">{{ c.count.toLocaleString() }}</td>
              <td>
                <div class="pct-bar">
                  <div class="pct-fill" :style="{ width: c.pct + '%' }"></div>
                  <span>{{ c.pct }}%</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ====== 数据来源分布 ====== -->
    <div class="section" v-if="!loading && stats?.by_source">
      <h3 class="section-title">数据来源分布</h3>
      <div class="source-cards">
        <div class="source-card" v-for="s in stats.by_source" :key="s.source">
          <div class="sc-icon">
            {{ s.source === 'zhilian' ? '◉' : s.source === 'boss' ? '◆' : '●' }}
          </div>
          <div class="sc-name">{{ s.source === 'zhilian' ? '智联招聘' : s.source === 'boss' ? 'BOSS直聘' : s.source === 'lagou' ? '拉勾网' : s.source }}</div>
          <div class="sc-count">{{ s.count.toLocaleString() }} 条</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---- 面板通用 ---- */
.panel {
  background: var(--bg-card); border-radius: var(--radius);
  box-shadow: var(--shadow); margin-bottom: 28px; overflow: hidden;
}
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px; border-bottom: 1px solid var(--border);
}
.panel-title { font-size: 15px; font-weight: 600; color: var(--text-1); }

/* 状态徽章 */
.status-badge {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: 500;
}
.status-badge.idle    { background: var(--green-soft); color: var(--green); }
.status-badge.running { background: var(--primary-soft); color: var(--primary); }
.status-dot {
  width: 7px; height: 7px; border-radius: 50%; background: currentColor;
}
.status-badge.running .status-dot { animation: blink 1s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* 爬虫主体：左右布局 */
.crawl-body { display: flex; gap: 0; min-height: 320px; }
.crawl-config { width: 340px; padding: 20px 24px; border-right: 1px solid var(--border); }
.crawl-log    { flex: 1; display: flex; flex-direction: column; }

/* 表单 */
.form-group  { margin-bottom: 14px; }
.form-label  { display: block; font-size: 12px; color: var(--text-3); margin-bottom: 6px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
.form-select,.form-input {
  width: 100%; padding: 9px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg-page); color: var(--text-1); font-size: 13px; outline: none;
}
.form-select:focus,.form-input:focus { border-color: var(--primary); }
.form-row { display: flex; gap: 12px; }

/* 数据源选择器 */
.source-selector { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.source-option {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 12px; border-radius: 8px; border: 2px solid var(--border);
  cursor: pointer; transition: all 0.2s; background: var(--bg-page);
}
.source-option:hover:not(.disabled) { border-color: var(--primary-light); }
.source-option.active { background: var(--primary-soft); }
.source-option.disabled { opacity: 0.4; cursor: not-allowed; }
.so-icon { font-size: 16px; }
.so-name { font-size: 13px; font-weight: 500; color: var(--text-1); }

/* 按钮 */
.btn-row { display: flex; gap: 10px; margin-top: 6px; }
.btn-start,.btn-stop {
  flex: 1; padding: 10px 20px; border-radius: 8px; border: none;
  font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-start { background: var(--primary); color: #fff; }
.btn-start:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); }
.btn-start:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-stop  { background: var(--red-soft); color: var(--red); }
.btn-stop:hover:not(:disabled) { background: #F0D0D0; }
.btn-stop:disabled { opacity: 0.3; cursor: not-allowed; }

/* 日志 */
.log-header {
  padding: 12px 20px; font-size: 12px; color: var(--text-3);
  font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
}
.log-body { flex: 1; padding: 12px 16px; overflow-y: auto; max-height: 260px; font-family: 'Consolas','Courier New',monospace; font-size: 12px; }
.log-empty { color: var(--text-3); text-align: center; padding: 40px 0; }
.log-line { display: flex; gap: 10px; padding: 4px 0; border-bottom: 1px solid rgba(128,128,128,0.06); }
.log-time { color: var(--text-3); white-space: nowrap; min-width: 70px; }
.log-msg  { color: var(--text-2); }
.log-info  .log-msg { color: var(--text-2); }
.log-success .log-msg { color: var(--green); }
.log-error .log-msg { color: var(--red); }
.log-warn  .log-msg { color: var(--orange); }

/* ---- 表格 ---- */
.section { margin-top: 28px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--text-2); }
.data-table-wrap { background: var(--bg-card); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; }
.data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.data-table th { text-align: left; padding: 12px 20px; background: var(--bg-sidebar); color: var(--text-2); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
.data-table td { padding: 12px 20px; border-top: 1px solid var(--border); color: var(--text-1); }
.td-rank { color: var(--text-3); width: 40px; }
.td-num  { font-weight: 500; }
.pct-bar { display: flex; align-items: center; gap: 8px; }
.pct-fill { height: 6px; border-radius: 3px; background: var(--primary); min-width: 2px; transition: width 0.5s; }

/* ---- 来源卡片 ---- */
.source-cards { display: flex; gap: 16px; flex-wrap: wrap; }
.source-card {
  flex: 1; min-width: 160px; background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 24px 16px; box-shadow: var(--shadow); text-align: center;
  transition: transform 0.2s;
}
.source-card:hover { transform: translateY(-2px); }
.sc-icon  { font-size: 28px; margin-bottom: 8px; }
.sc-name  { font-size: 14px; color: var(--text-2); margin-bottom: 6px; }
.sc-count { font-size: 24px; font-weight: 700; color: var(--primary); }

/* 详情抓取进度 */
.detail-stats { padding: 12px 0; }
.ds-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; color: var(--text-2); }
.dsv { font-weight: 600; color: var(--text-1); }

/* ---- 响应式 ---- */
@media (max-width: 768px) {
  .crawl-body { flex-direction: column; }
  .crawl-config { width: 100%; border-right: none; border-bottom: 1px solid var(--border); }
  .source-selector { grid-template-columns: 1fr 1fr; }
}
</style>
