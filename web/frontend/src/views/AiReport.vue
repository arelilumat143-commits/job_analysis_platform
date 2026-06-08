<!-- ============================================================
 AiReport v2 — AI 招聘市场分析报告（结构化报告版）
 从"聊天问答"升级为"专业数据分析报告"
 数据来源：/api/analysis/market-insight + /api/jobs/stats + /api/analysis/*
 ============================================================ -->
<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'
import { useChart } from '../composables/useChart.js'

const store = useAppStore()
const { get, post } = useApi()
const { init: initChart, setOption: setChart, readCssVar } = useChart()

const loading = ref(true)
const insight = ref(null)
const stats = ref(null)
const salaryData = ref(null)
const skillData = ref(null)
const industryData = ref(null)
const experienceData = ref(null)
const educationData = ref(null)

// ---- AI 对话状态 ----
const chatApiKey = ref(store.aiApiKey || '')
const chatProvider = ref(store.aiProvider || 'siliconflow')
const chatModel = ref('')
const chatInput = ref('')
const chatSending = ref(false)
const chatMessages = ref([])
const chatShowConfig = ref(false)
const chatError = ref('')

// 从 localStorage 恢复配置
try {
  const saved = localStorage.getItem('ai_chat_config')
  if (saved) {
    const cfg = JSON.parse(saved)
    chatApiKey.value = cfg.apiKey || ''
    chatProvider.value = cfg.provider || 'siliconflow'
    chatModel.value = cfg.model || ''
  }
  // 恢复聊天记录
  const savedMsgs = localStorage.getItem('ai_chat_messages')
  if (savedMsgs) {
    chatMessages.value = JSON.parse(savedMsgs)
  }
} catch (_) {}

// 保存配置
function saveChatConfig() {
  store.aiApiKey = chatApiKey.value
  store.aiProvider = chatProvider.value
  localStorage.setItem('ai_chat_config', JSON.stringify({
    apiKey: chatApiKey.value,
    provider: chatProvider.value,
    model: chatModel.value,
  }))
  chatShowConfig.value = false
}

// 监听聊天记录变化，自动持久化到 localStorage
watch(chatMessages, (msgs) => {
  // 不保存 pending 状态的占位消息
  const toSave = msgs.filter(m => !m.pending)
  if (toSave.length > 0) {
    localStorage.setItem('ai_chat_messages', JSON.stringify(toSave))
  } else {
    localStorage.removeItem('ai_chat_messages')
  }
}, { deep: true })

// ---- 报告生成时间 ----
const reportTime = computed(() => {
  return new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
})

// ---- 加载所有数据 ----
async function loadData() {
  loading.value = true
  const [ins, st, sa, sk, ind, exp, edu] = await Promise.all([
    get('/api/analysis/market-insight'),
    get('/api/jobs/stats'),
    get('/api/analysis/salary'),
    get('/api/analysis/skill'),
    get('/api/analysis/industry'),
    get('/api/analysis/experience'),
    get('/api/analysis/education'),
  ])
  if (ins) insight.value = ins
  if (st) stats.value = st
  if (sa) salaryData.value = sa
  if (sk) skillData.value = sk
  if (ind) industryData.value = ind
  if (exp) experienceData.value = exp
  if (edu) educationData.value = edu
  loading.value = false
  await nextTick()
  renderCharts()
}

// ---- 市场健康度颜色 ----
const healthColor = computed(() => {
  const s = insight.value?.market_health?.score || 0
  if (s >= 80) return 'var(--green)'
  if (s >= 60) return 'var(--primary)'
  if (s >= 40) return 'var(--orange)'
  return 'var(--red)'
})

// ---- 图表渲染 ----
function renderCharts() {
  renderExpChart()
  renderEduChart()
}

function renderExpChart() {
  const c = initChart('chart-exp')
  if (!c || !experienceData.value?.length) return
  const data = experienceData.value
  setChart('chart-exp', {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 10, bottom: 60 },
    xAxis: {
      type: 'category', data: data.map(x => x.experience),
      axisLabel: { rotate: 25, fontSize: 11, color: readCssVar('--text-2') },
    },
    yAxis: {
      type: 'value', name: '职位数',
      splitLine: { lineStyle: { color: readCssVar('--border'), type: 'dashed' } },
    },
    series: [{
      type: 'bar', data: data.map(x => x.count),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: readCssVar('--primary') },
          { offset: 1, color: readCssVar('--primary-light') }
        ]),
        borderRadius: [6, 6, 0, 0],
      },
      barWidth: '50%',
    }],
    backgroundColor: 'transparent',
  })
}

function renderEduChart() {
  const c = initChart('chart-edu')
  if (!c || !educationData.value?.length) return
  const data = educationData.value
  const colors = [readCssVar('--primary'), readCssVar('--green'), readCssVar('--orange'), readCssVar('--purple'), readCssVar('--red')]
  setChart('chart-edu', {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['50%', '55%'],
      data: data.map((x, i) => ({ name: x.education, value: x.count, itemStyle: { color: colors[i % colors.length] } })),
      label: { color: readCssVar('--text-2'), fontSize: 12 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' } },
    }],
    backgroundColor: 'transparent',
  })
}

// ---- 技能需求等级 ----
function skillLevel(idx) {
  if (idx < 5) return 'hot'
  if (idx < 15) return 'warm'
  return 'normal'
}

import * as echarts from 'echarts'

// ---- AI 对话方法 ----

/** 发送消息 */
async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || chatSending.value) return

  if (!chatApiKey.value) {
    chatError.value = '请先配置 API Key'
    chatShowConfig.value = true
    return
  }

  chatError.value = ''
  chatMessages.value.push({ role: 'user', content: text })
  chatInput.value = ''
  chatSending.value = true

  // 添加占位回复
  chatMessages.value.push({ role: 'assistant', content: '', pending: true })

  try {
    const res = await post('/api/ai/chat', {
      messages: chatMessages.value.filter(m => !m.pending),
      provider: chatProvider.value,
      api_key: chatApiKey.value,
      model: chatModel.value || null,
      include_context: true,
    })

    // 替换占位消息
    const last = chatMessages.value[chatMessages.value.length - 1]
    if (res?.reply) {
      last.content = res.reply
    } else {
      last.content = '抱歉，AI 暂时无法回复。请检查 API Key 和网络连接。'
    }
    last.pending = false
  } catch (e) {
    const last = chatMessages.value[chatMessages.value.length - 1]
    last.content = '请求失败，请检查 API Key 和网络连接是否正常。'
    last.pending = false
    chatError.value = '请求失败: ' + (e.message || '未知错误')
  }
  chatSending.value = false
}

/** 按 Enter 发送 */
function onChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendChat()
  }
}

/** 清空对话 */
function clearChat() {
  chatMessages.value = []
  chatError.value = ''
}

/** 简易 Markdown 渲染（仅处理粗体、标题、列表、代码） */
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // 粗体
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // ### 标题
    .replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
    // 无序列表
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    // 数字列表
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // 换行
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
  return '<p>' + html + '</p>'
}

onMounted(() => loadData())
</script>

<template>
  <div class="page">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-wrap">
      <div class="pulse-dot"></div>
      <span>正在生成分析报告...</span>
    </div>

    <template v-else>
      <!-- ====== 报告头部 ====== -->
      <div class="report-header">
        <div class="report-cover">
          <div class="cover-badge">AI 生成</div>
          <h1 class="cover-title">招聘市场数据分析报告</h1>
          <div class="cover-meta">
            <span>基于 {{ stats?.total?.toLocaleString() || '--' }} 条真实职位数据</span>
            <span class="meta-sep">|</span>
            <span>{{ reportTime }}</span>
          </div>
        </div>
      </div>

      <!-- ====== 一、执行摘要 ====== -->
      <section class="report-section">
        <h2 class="section-title"><span class="section-num">01</span> 执行摘要</h2>
        <div class="exec-summary">
          <p>{{ insight?.ai_summary || '数据加载中...' }}</p>
        </div>

        <!-- 关键指标行 -->
        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-value">{{ stats?.total?.toLocaleString() || '--' }}</div>
            <div class="kpi-label">市场职位总量</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value accent">{{ insight?.salary_overview?.avg_salary?.toFixed(1) || '--' }}K</div>
            <div class="kpi-label">市场平均月薪</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value" :style="{ color: healthColor }">{{ insight?.market_health?.score || '--' }}</div>
            <div class="kpi-label">{{ insight?.market_health?.label || '市场健康度' }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-value">{{ insight?.salary_overview?.high_salary_pct || '--' }}%</div>
            <div class="kpi-label">高薪岗位占比 (30K+)</div>
          </div>
        </div>
      </section>

      <!-- ====== 二、关键发现 ====== -->
      <section class="report-section" v-if="insight?.key_findings?.length">
        <h2 class="section-title"><span class="section-num">02</span> 关键发现</h2>
        <div class="findings-grid">
          <div class="finding-card" v-for="(f, i) in insight.key_findings" :key="i">
            <span class="finding-num">{{ i + 1 }}</span>
            <span class="finding-text">{{ f }}</span>
          </div>
        </div>
      </section>

      <!-- ====== 三、市场健康度 ====== -->
      <section class="report-section" v-if="insight?.market_health">
        <h2 class="section-title"><span class="section-num">03</span> 市场健康度评估</h2>
        <div class="health-section">
          <div class="health-gauge">
            <svg viewBox="0 0 120 120" width="140" height="140">
              <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" stroke-width="10"/>
              <circle cx="60" cy="60" r="52" fill="none" :stroke="healthColor" stroke-width="10"
                stroke-linecap="round" stroke-dasharray="326.7"
                :stroke-dashoffset="326.7 - (326.7 * (insight.market_health.score || 0) / 100)"
                transform="rotate(-90 60 60)" style="transition: stroke-dashoffset 1.2s ease"/>
              <text x="60" y="56" text-anchor="middle" fill="var(--text-1)" font-size="28" font-weight="800">{{ insight.market_health.score }}</text>
              <text x="60" y="76" text-anchor="middle" fill="var(--text-3)" font-size="12">{{ insight.market_health.label }}</text>
            </svg>
          </div>
          <div class="health-factors">
            <div class="hf-item" v-for="f in insight.market_health.factors || []" :key="f">
              <span class="hf-dot" :style="{ background: healthColor }"></span>
              {{ f }}
            </div>
          </div>
        </div>
      </section>

      <!-- ====== 四、城市分析 ====== -->
      <section class="report-section" v-if="insight?.top_cities?.length">
        <h2 class="section-title"><span class="section-num">04</span> 城市分布与薪资对比</h2>
        <div class="city-table-wrap">
          <table class="city-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>城市</th>
                <th>职位数量</th>
                <th>占比</th>
                <th>平均薪资</th>
                <th>热度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in insight.top_cities.slice(0, 10)" :key="c.city">
                <td><span class="ct-rank" :class="'r' + (i + 1)">{{ i + 1 }}</span></td>
                <td class="ct-name">{{ c.city }}</td>
                <td>{{ c.count.toLocaleString() }}</td>
                <td>{{ stats ? (c.count / stats.total * 100).toFixed(1) : '--' }}%</td>
                <td class="ct-salary">{{ c.avg_salary || '--' }}K</td>
                <td>
                  <div class="ct-bar-bg">
                    <div class="ct-bar" :style="{ width: stats ? (c.count / (insight.top_cities[0]?.count || 1) * 100) + '%' : '0%' }"></div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ====== 五、薪资分析 ====== -->
      <section class="report-section" v-if="salaryData">
        <h2 class="section-title"><span class="section-num">05</span> 薪资结构分析</h2>
        <div class="salary-stats">
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.mean?.toFixed(1) }}K</div>
            <div class="ss-lbl">平均值</div>
          </div>
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.median?.toFixed(1) }}K</div>
            <div class="ss-lbl">中位数</div>
          </div>
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.q25?.toFixed(1) }}K</div>
            <div class="ss-lbl">25%分位</div>
          </div>
          <div class="ss-item" v-if="salaryData.basic_stats">
            <div class="ss-val">{{ salaryData.basic_stats.q75?.toFixed(1) }}K</div>
            <div class="ss-lbl">75%分位</div>
          </div>
          <div class="ss-item">
            <div class="ss-val">{{ salaryData.basic_stats?.count?.toLocaleString() || '--' }}</div>
            <div class="ss-lbl">样本量</div>
          </div>
        </div>
      </section>

      <!-- ====== 六、技能需求 ====== -->
      <section class="report-section" v-if="skillData?.top_skills?.length">
        <h2 class="section-title"><span class="section-num">06</span> 热门技能需求</h2>
        <div class="skills-cloud">
          <span class="sc-item" v-for="(s, i) in skillData.top_skills.slice(0, 24)" :key="s.skill"
            :class="'sc-' + skillLevel(i)">
            {{ s.skill }}
            <small>{{ s.count }}</small>
          </span>
        </div>
        <div class="sc-empty" v-if="!skillData.top_skills.length">
          技能数据尚未采集，请先运行详情页爬虫填充技能字段。
        </div>
      </section>

      <!-- ====== 七、经验与学历 ====== -->
      <section class="report-section">
        <h2 class="section-title"><span class="section-num">07</span> 经验与学历要求</h2>
        <div class="chart-row">
          <div class="chart-half">
            <h4 class="chart-subtitle">经验要求分布</h4>
            <div id="chart-exp" style="width:100%;height:280px"></div>
            <div class="chart-empty" v-if="!experienceData?.length">暂无经验要求数据</div>
          </div>
          <div class="chart-half">
            <h4 class="chart-subtitle">学历要求分布</h4>
            <div id="chart-edu" style="width:100%;height:280px"></div>
            <div class="chart-empty" v-if="!educationData?.length">暂无学历要求数据</div>
          </div>
        </div>
      </section>

      <!-- ====== 八、行业概览 ====== -->
      <section class="report-section" v-if="industryData?.length">
        <h2 class="section-title"><span class="section-num">08</span> 行业分布</h2>
        <div class="industry-list">
          <div class="ind-item" v-for="ind in industryData.slice(0, 10)" :key="ind.industry">
            <span class="ind-name">{{ ind.industry }}</span>
            <span class="ind-count">{{ ind.count?.toLocaleString() || '--' }} 条</span>
          </div>
        </div>
      </section>

      <!-- ====== 九、建议与展望 ====== -->
      <section class="report-section">
        <h2 class="section-title"><span class="section-num">09</span> 建议与展望</h2>
        <div class="recommendations">
          <div class="rec-item">
            <div class="rec-icon">数据</div>
            <div class="rec-content">
              <div class="rec-title">扩充数据来源</div>
              <div class="rec-desc">当前数据以智联招聘为主，建议增加 BOSS直聘、拉勾网等渠道，提升数据多样性和代表性。</div>
            </div>
          </div>
          <div class="rec-item">
            <div class="rec-icon">技能</div>
            <div class="rec-content">
              <div class="rec-title">完善技能标签</div>
              <div class="rec-desc">运行详情页爬虫补充技能、行业、经验等字段，当前大量职位缺少结构化标签。</div>
            </div>
          </div>
          <div class="rec-item">
            <div class="rec-icon">AI</div>
            <div class="rec-content">
              <div class="rec-title">接入 AI 大模型</div>
              <div class="rec-desc">当前使用本地规则引擎生成报告，接入 DeepSeek API 可实现更深入的个性化分析。</div>
            </div>
          </div>
          <div class="rec-item">
            <div class="rec-icon">趋势</div>
            <div class="rec-content">
              <div class="rec-title">增加时间维度</div>
              <div class="rec-desc">定期采集数据，建立时间序列分析能力，追踪市场薪资和技能需求变化趋势。</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ====== 十、AI 智能对话 ====== -->
      <section class="report-section">
        <h2 class="section-title">
          <span class="section-num">10</span> AI 智能对话
          <span class="section-badge">大模型</span>
        </h2>

        <!-- API 配置区 -->
        <div class="chat-config" v-if="chatShowConfig || !chatApiKey">
          <div class="chat-config-hint">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            <span>配置大模型 API Key 后即可使用 AI 对话功能（Key 仅保存在本地浏览器）</span>
          </div>
          <div class="chat-config-row">
            <select v-model="chatProvider" class="chat-select">
              <option value="siliconflow">硅基流动（推荐）</option>
              <option value="deepseek">DeepSeek</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
            </select>
            <input v-model="chatApiKey" type="password" class="chat-key-input"
              placeholder="粘贴 API Key，如 sk-xxxxxxxx" @focus="chatError=''" />
            <input v-model="chatModel" type="text" class="chat-model-input"
              :placeholder="chatProvider === 'siliconflow' ? '模型 (默认 DeepSeek-V3)' : '模型 (可选)'" />
            <button class="chat-config-btn" @click="saveChatConfig">保存配置</button>
          </div>
          <div class="chat-config-links">
            免费获取 Key：
            <a href="https://siliconflow.cn" target="_blank">硅基流动</a> ·
            <a href="https://platform.deepseek.com" target="_blank">DeepSeek</a>
          </div>
        </div>

        <!-- 已配置状态条 -->
        <div class="chat-status" v-else>
          <span class="chat-status-dot"></span>
          <span>已配置 {{ chatProvider === 'siliconflow' ? '硅基流动' : chatProvider === 'deepseek' ? 'DeepSeek' : chatProvider === 'openai' ? 'OpenAI' : 'Gemini' }}
            · Key: {{ chatApiKey.slice(0, 8) }}...</span>
          <button class="chat-status-edit" @click="chatShowConfig = true">修改</button>
        </div>

        <!-- 对话区 -->
        <div class="chat-box">
          <div class="chat-messages" ref="chatMsgRef">
            <div v-if="!chatMessages.length && !chatSending" class="chat-welcome">
              <div class="chat-welcome-icon">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <div class="chat-welcome-title">招聘 AI 助手</div>
              <div class="chat-welcome-desc">
                我可以帮你分析招聘市场数据，解答关于薪资、技能、城市、行业等方面的问题。<br/>
                试试问我：<br/>
                <button class="chat-quick-q" @click="chatInput='北京和上海的Python岗位薪资对比如何？'; sendChat()">北京和上海的Python岗位薪资对比如何？</button>
                <button class="chat-quick-q" @click="chatInput='哪些技能目前市场需求最大？'; sendChat()">哪些技能目前市场需求最大？</button>
                <button class="chat-quick-q" @click="chatInput='应届生应该学什么技术栈比较好就业？'; sendChat()">应届生应该学什么技术栈比较好就业？</button>
              </div>
            </div>

            <div class="chat-msg" v-for="(m, i) in chatMessages" :key="i" :class="'msg-' + m.role">
              <div class="msg-avatar">
                <template v-if="m.role === 'assistant'">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2">
                    <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/>
                    <path d="M12 14c-6 0-8 3-8 5v1h16v-1c0-2-2-5-8-5z"/>
                    <circle cx="9" cy="9" r="1" fill="currentColor"/><circle cx="15" cy="9" r="1" fill="currentColor"/>
                  </svg>
                </template>
                <template v-else>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-2)" stroke-width="2">
                    <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-7 8-7s8 3 8 7"/>
                  </svg>
                </template>
              </div>
              <div class="msg-bubble">
                <div v-if="m.pending" class="msg-pending">
                  <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
                </div>
                <div v-else class="msg-content" v-html="renderMarkdown(m.content)"></div>
              </div>
            </div>

            <div v-if="chatError" class="chat-err">{{ chatError }}</div>
          </div>

          <!-- 输入区 -->
          <div class="chat-input-row">
            <textarea v-model="chatInput" class="chat-textarea"
              placeholder="输入你的问题，按 Enter 发送..."
              :disabled="chatSending" rows="2"
              @keydown="onChatKeydown"></textarea>
            <button class="chat-send-btn" @click="sendChat" :disabled="chatSending || !chatInput.trim()">
              <svg v-if="!chatSending" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
              <span v-else class="sending-spin"></span>
            </button>
          </div>
          <div class="chat-input-hint">
            <button class="chat-clear-btn" v-if="chatMessages.length" @click="clearChat">清空对话</button>
            <span>AI 回答仅供参考，数据基于 {{ stats?.total?.toLocaleString() || '22,908' }} 条真实招聘信息</span>
          </div>
        </div>
      </section>

      <!-- 报告脚注 -->
      <div class="report-footer">
        <p>本报告由 AI 自动生成，数据来源为招聘平台公开职位信息。仅供学习参考，不构成职业建议。</p>
        <p>报告生成时间：{{ reportTime }} | 招聘数据分析平台</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ===== 加载 ===== */
.loading-wrap {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 0; color: var(--text-3);
}
.pulse-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: var(--primary); animation: pulse 1.2s infinite;
}
@keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1.2)} }

/* ===== 报告头部 ===== */
.report-header {
  background: linear-gradient(135deg, var(--primary-soft), var(--bg-card));
  border-radius: var(--radius); padding: 40px 36px; margin-bottom: 28px;
  text-align: center; box-shadow: var(--shadow);
}
.cover-badge {
  display: inline-block; padding: 4px 16px; border-radius: 16px;
  background: var(--primary); color: var(--text-inverse);
  font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; margin-bottom: 16px;
}
.cover-title {
  font-size: 28px; font-weight: 800; color: var(--text-1);
  margin: 0 0 12px; letter-spacing: 0.02em;
}
.cover-meta { font-size: 14px; color: var(--text-3); }
.meta-sep { margin: 0 10px; color: var(--border); }

/* ===== 报告区块 ===== */
.report-section { margin-bottom: 32px; }
.section-title {
  font-size: 20px; font-weight: 700; color: var(--text-1);
  margin: 0 0 18px; padding-bottom: 12px;
  border-bottom: 2px solid var(--border); display: flex; align-items: center; gap: 12px;
}
.section-num {
  font-size: 14px; font-weight: 700; color: var(--primary);
  background: var(--primary-soft); padding: 4px 10px; border-radius: 6px;
}

/* 执行摘要 */
.exec-summary {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px 24px; margin-bottom: 20px;
  border-left: 4px solid var(--primary); box-shadow: var(--shadow);
}
.exec-summary p {
  font-size: 15px; line-height: 1.9; color: var(--text-2); margin: 0;
}

/* KPI 行 */
.kpi-row {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
}
.kpi-card {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px; text-align: center; box-shadow: var(--shadow);
}
.kpi-value {
  font-size: 28px; font-weight: 800; color: var(--text-1); margin-bottom: 4px;
}
.kpi-value.accent { color: var(--primary); }
.kpi-label { font-size: 12px; color: var(--text-3); }

/* 关键发现 */
.findings-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;
}
.finding-card {
  display: flex; align-items: flex-start; gap: 12px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 16px 20px; box-shadow: var(--shadow);
  border: 1px solid var(--border); transition: all 0.2s;
}
.finding-card:hover { border-color: var(--primary-light); transform: translateY(-1px); }
.finding-num {
  width: 28px; height: 28px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: var(--primary-soft); color: var(--primary);
  font-size: 14px; font-weight: 700; flex-shrink: 0;
}
.finding-text { font-size: 14px; color: var(--text-2); line-height: 1.7; }

/* 市场健康度 */
.health-section {
  display: flex; align-items: center; gap: 40px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 28px 32px; box-shadow: var(--shadow);
}
.health-gauge { flex-shrink: 0; }
.health-factors { display: flex; flex-direction: column; gap: 8px; }
.hf-item {
  font-size: 13px; color: var(--text-2); display: flex; align-items: center; gap: 10px;
}
.hf-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

/* 城市表格 */
.city-table-wrap { background: var(--bg-card); border-radius: var(--radius-sm); box-shadow: var(--shadow); overflow: hidden; }
.city-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.city-table th {
  text-align: left; padding: 12px 16px; background: var(--bg-sidebar);
  color: var(--text-2); font-weight: 500; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.city-table td { padding: 12px 16px; border-top: 1px solid var(--border); color: var(--text-1); }
.ct-rank {
  width: 26px; height: 26px; border-radius: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; background: var(--bg-page); color: var(--text-3);
}
.ct-rank.r1 { background: var(--primary-soft); color: var(--primary); }
.ct-rank.r2 { background: var(--green-soft); color: var(--green); }
.ct-rank.r3 { background: var(--orange); color: var(--text-inverse); opacity: 0.7; }
.ct-name { font-weight: 500; }
.ct-salary { color: var(--primary); font-weight: 600; }
.ct-bar-bg { width: 100%; height: 8px; border-radius: 4px; background: var(--bg-page); }
.ct-bar { height: 100%; border-radius: 4px; background: var(--primary); transition: width 0.6s ease; }

/* 薪资统计 */
.salary-stats {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px;
}
.ss-item {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px; text-align: center; box-shadow: var(--shadow);
}
.ss-val { font-size: 22px; font-weight: 700; color: var(--primary); }
.ss-lbl { font-size: 11px; color: var(--text-3); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.04em; }

/* 技能云 */
.skills-cloud {
  display: flex; flex-wrap: wrap; gap: 10px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px 24px; box-shadow: var(--shadow);
}
.sc-item {
  padding: 6px 14px; border-radius: 8px; font-size: 14px; font-weight: 500;
  display: inline-flex; align-items: center; gap: 6px;
}
.sc-item small { font-size: 11px; opacity: 0.7; }
.sc-hot { background: var(--red-soft); color: var(--red); font-size: 16px; }
.sc-warm { background: var(--primary-soft); color: var(--primary); }
.sc-normal { background: var(--bg-page); color: var(--text-3); }
.sc-empty { color: var(--text-3); font-size: 13px; padding: 16px; }

/* 图表行 */
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.chart-half {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 20px 24px; box-shadow: var(--shadow);
}
.chart-subtitle { font-size: 14px; font-weight: 600; color: var(--text-1); margin: 0 0 8px; }
.chart-empty { color: var(--text-3); font-size: 13px; padding: 20px; text-align: center; }

/* 行业列表 */
.industry-list {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 16px 20px; box-shadow: var(--shadow);
  display: flex; flex-wrap: wrap; gap: 8px;
}
.ind-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px; border-radius: 8px; background: var(--bg-page);
}
.ind-name { font-size: 13px; color: var(--text-1); font-weight: 500; }
.ind-count { font-size: 12px; color: var(--text-3); }

/* 建议 */
.recommendations {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px;
}
.rec-item {
  display: flex; gap: 14px; background: var(--bg-card);
  border-radius: var(--radius-sm); padding: 20px; box-shadow: var(--shadow);
  border: 1px solid var(--border); transition: all 0.2s;
}
.rec-item:hover { border-color: var(--primary-light); }
.rec-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  background: var(--primary-soft); color: var(--primary);
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.rec-title { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.rec-desc { font-size: 12px; color: var(--text-3); line-height: 1.6; }

/* 脚注 */
.report-footer {
  margin-top: 40px; padding-top: 24px;
  border-top: 2px solid var(--border); text-align: center;
}
.report-footer p {
  font-size: 12px; color: var(--text-3); margin: 0 0 4px;
}

  /* ===== AI 对话面板 ===== */
  .section-badge {
    font-size: 11px; font-weight: 600; color: var(--primary);
    background: var(--primary-soft); padding: 3px 10px; border-radius: 12px;
  }

  /* API 配置 */
  .chat-config {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 20px 24px; margin-bottom: 16px;
  }
  .chat-config-hint {
    display: flex; align-items: center; gap: 10px;
    font-size: 13px; color: var(--text-2); margin-bottom: 14px;
  }
  .chat-config-hint svg { flex-shrink: 0; color: var(--orange); }
  .chat-config-row {
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  }
  .chat-select, .chat-key-input, .chat-model-input {
    padding: 9px 14px; border: 1px solid var(--border);
    border-radius: 8px; font-size: 13px; background: var(--bg-page);
    color: var(--text-1); outline: none; transition: border-color 0.2s;
  }
  .chat-select:focus, .chat-key-input:focus, .chat-model-input:focus {
    border-color: var(--primary);
  }
  .chat-select { min-width: 160px; }
  .chat-key-input { flex: 1; min-width: 220px; }
  .chat-model-input { width: 180px; }
  .chat-config-btn {
    padding: 9px 20px; background: var(--primary); color: var(--text-inverse);
    border: none; border-radius: 8px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: opacity 0.2s;
  }
  .chat-config-btn:hover { opacity: 0.85; }
  .chat-config-links {
    margin-top: 10px; font-size: 12px; color: var(--text-3);
  }
  .chat-config-links a { color: var(--primary); text-decoration: none; }
  .chat-config-links a:hover { text-decoration: underline; }

  /* 配置状态条 */
  .chat-status {
    display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
    padding: 10px 16px; background: var(--green-soft); border-radius: 8px;
    font-size: 13px; color: var(--green);
  }
  .chat-status-dot {
    width: 8px; height: 8px; border-radius: 50%; background: var(--green); flex-shrink: 0;
  }
  .chat-status-edit {
    margin-left: auto; padding: 4px 12px;
    background: transparent; border: 1px solid var(--green);
    color: var(--green); border-radius: 6px; font-size: 12px;
    cursor: pointer; transition: all 0.2s;
  }
  .chat-status-edit:hover { background: var(--green); color: var(--text-inverse); }

  /* 对话区 */
  .chat-box {
    background: var(--bg-card); border-radius: var(--radius-sm);
    box-shadow: var(--shadow); overflow: hidden;
  }
  .chat-messages {
    max-height: 480px; overflow-y: auto; padding: 20px 24px;
  }
  .chat-messages::-webkit-scrollbar { width: 5px; }
  .chat-messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* 欢迎区 */
  .chat-welcome { text-align: center; padding: 20px 0; }
  .chat-welcome-icon { margin-bottom: 12px; opacity: 0.7; }
  .chat-welcome-title { font-size: 18px; font-weight: 700; color: var(--text-1); margin-bottom: 8px; }
  .chat-welcome-desc { font-size: 13px; color: var(--text-3); line-height: 1.8; }
  .chat-quick-q {
    display: inline-block; margin: 4px 4px; padding: 6px 14px;
    background: var(--primary-soft); color: var(--primary);
    border: none; border-radius: 16px; font-size: 12px;
    cursor: pointer; transition: all 0.2s;
  }
  .chat-quick-q:hover { background: var(--primary); color: var(--text-inverse); }

  /* 消息 */
  .chat-msg { display: flex; gap: 12px; margin-bottom: 18px; }
  .chat-msg.msg-user { flex-direction: row-reverse; }
  .msg-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: var(--bg-page); flex-shrink: 0;
  }
  .msg-assistant .msg-avatar { background: var(--primary-soft); }
  .msg-bubble { max-width: 78%; }
  .msg-user .msg-bubble { text-align: right; }
  .msg-content {
    font-size: 14px; line-height: 1.75; color: var(--text-1);
    padding: 12px 16px; border-radius: 14px;
    background: var(--bg-page); white-space: pre-wrap; word-break: break-word;
  }
  .msg-user .msg-content {
    background: var(--primary-soft); color: var(--text-1);
  }
  .msg-content :deep(p) { margin: 0 0 6px; }
  .msg-content :deep(ul) { margin: 4px 0; padding-left: 18px; }
  .msg-content :deep(li) { margin: 2px 0; }
  .msg-content :deep(code) {
    padding: 2px 6px; border-radius: 4px;
    background: var(--border); font-size: 0.9em;
  }
  .msg-content :deep(strong) { font-weight: 700; color: var(--text-1); }
  .msg-content :deep(h3) { font-size: 15px; font-weight: 700; margin: 8px 0 4px; }
  .msg-content :deep(h4) { font-size: 14px; font-weight: 600; margin: 6px 0 4px; }

  /* 打字动画 */
  .msg-pending { padding: 12px 16px; }
  .typing-dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: var(--text-3); margin-right: 4px;
    animation: typingBounce 1.4s infinite;
  }
  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes typingBounce {
    0%,60%,100% { transform: translateY(0); opacity: 0.3; }
    30% { transform: translateY(-6px); opacity: 1; }
  }

  .chat-err {
    color: var(--red); font-size: 12px; padding: 8px 0; text-align: center;
  }

  /* 输入区 */
  .chat-input-row {
    display: flex; align-items: flex-end; gap: 10px;
    padding: 14px 20px; border-top: 1px solid var(--border);
    background: var(--bg-page);
  }
  .chat-textarea {
    flex: 1; padding: 10px 14px; border: 1px solid var(--border);
    border-radius: 10px; font-size: 13px; color: var(--text-1);
    background: var(--bg-card); outline: none; resize: none;
    font-family: inherit; transition: border-color 0.2s;
  }
  .chat-textarea:focus { border-color: var(--primary); }
  .chat-textarea:disabled { opacity: 0.5; }
  .chat-send-btn {
    width: 40px; height: 40px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    background: var(--primary); color: var(--text-inverse);
    border: none; cursor: pointer; transition: all 0.2s; flex-shrink: 0;
  }
  .chat-send-btn:hover:not(:disabled) { opacity: 0.85; transform: scale(1.05); }
  .chat-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .sending-spin {
    width: 16px; height: 16px; border: 2px solid var(--text-inverse);
    border-top-color: transparent; border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .chat-input-hint {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 20px 14px; font-size: 11px; color: var(--text-3);
    background: var(--bg-page);
  }
  .chat-clear-btn {
    padding: 2px 8px; background: transparent; border: 1px solid var(--border);
    color: var(--text-3); border-radius: 4px; font-size: 11px;
    cursor: pointer; transition: all 0.2s;
  }
  .chat-clear-btn:hover { border-color: var(--red); color: var(--red); }

@media (max-width: 768px) {
  .cover-title { font-size: 22px; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .findings-grid, .chart-row, .recommendations { grid-template-columns: 1fr; }
  .health-section { flex-direction: column; }
  .salary-stats { grid-template-columns: repeat(3, 1fr); }
  .chat-config-row { flex-direction: column; }
  .chat-select, .chat-key-input, .chat-model-input { width: 100%; min-width: 0; }
}
</style>
