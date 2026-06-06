<!-- ============================================================
 Recommend v3 — 岗位推荐页（可解释性增强版）
 算法：TF-IDF + SBERT 双引擎
 新增：分项贡献度分解 / 匹配因子可视化 / 学习建议
 接口：POST /api/matching/jobs
 ============================================================ -->
<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'

const store = useAppStore()
const { post } = useApi()

const loading = ref(false)
const matchResult = ref(null)
const hasSearched = ref(false)

// ---- 筛选条件 ----
const filters = ref({
  skills: 'Python,Django',
  city: '北京',
  salary_min: null,
  salary_max: null,
  top_n: 10,
})

// ---- 预设选项 ----
const cities = ['北京', '上海', '广州', '深圳', '杭州', '成都', '南京', '武汉', '西安', '郑州']

const quickSkills = [
  { label: 'Python', skills: 'Python,Django,Flask' },
  { label: 'Java',   skills: 'Java,Spring,MyBatis' },
  { label: '前端',   skills: 'JavaScript,Vue,React' },
  { label: '数据',   skills: 'SQL,Python,Spark' },
  { label: '运维',   skills: 'Linux,Docker,Kubernetes' },
  { label: 'AI',     skills: 'Python,PyTorch,TensorFlow' },
  { label: 'Go',     skills: 'Go,Linux,Docker' },
  { label: '全栈',   skills: 'Python,JavaScript,Vue,Docker' },
]

// ---- 学习路线建议（基于缺失技能的分类）----
const learningPaths = {
  'python': { title: 'Python 进阶', desc: '掌握 Django/Flask Web框架、异步编程、性能优化', icon: 'Python' },
  'java': { title: 'Java 生态', desc: '深入学习 Spring Boot、微服务架构、JVM 调优', icon: 'Java' },
  'javascript': { title: '前端工程化', desc: '学习 React/Vue3、TypeScript、构建工具链', icon: 'JS' },
  'docker': { title: '容器化部署', desc: '掌握 Docker + K8s、CI/CD 流水线、云原生', icon: 'DevOps' },
  'sql': { title: '数据库进阶', desc: 'SQL 优化、索引设计、分库分表策略', icon: 'DB' },
  'linux': { title: 'Linux 运维', desc: 'Shell 脚本、系统管理、网络配置', icon: 'Linux' },
  'tensorflow': { title: 'AI/ML 方向', desc: '深度学习框架、模型部署、MLOps', icon: 'AI' },
  'spark': { title: '大数据处理', desc: 'Spark/Hadoop 生态、数据管道、实时计算', icon: 'Data' },
  'react': { title: '现代前端', desc: 'React Hooks、状态管理、SSR/SSG', icon: 'FE' },
  'go': { title: 'Go 语言', desc: '并发编程、微服务、高性能后端', icon: 'Go' },
}

// ---- 匹配 ----
async function search() {
  loading.value = true
  hasSearched.value = true
  matchResult.value = null

  const skillsArray = filters.value.skills
    .split(/[,，、;；]/)
    .map(s => s.trim())
    .filter(s => s.length > 0)

  if (!skillsArray.length) {
    loading.value = false
    return
  }

  const body = {
    skills: skillsArray,
    city: filters.value.city,
  }
  if (filters.value.salary_min) body.salary_min = filters.value.salary_min
  if (filters.value.salary_max) body.salary_max = filters.value.salary_max
  body.top_n = filters.value.top_n

  const result = await post('/api/matching/jobs', body)
  if (result) matchResult.value = result
  loading.value = false
}

function fillSkills(skills) { filters.value.skills = skills }

function formatSalary(item) {
  if (!item.salary_min && !item.salary_max) return '面议'
  const min = item.salary_min ? item.salary_min + 'K' : ''
  const max = item.salary_max ? item.salary_max + 'K' : ''
  return min && max ? min + ' - ' + max : (min || max)
}

function scoreColor(score) {
  if (score >= 70) return 'var(--green)'
  if (score >= 50) return 'var(--orange)'
  return 'var(--text-3)'
}

// ---- 分项贡献度排序（从高到低）----
function sortedBreakdown(item) {
  if (!item.score_breakdown) return []
  const bd = item.score_breakdown
  const labels = { tfidf: '关键词', sbert: '语义', skill: '技能', city: '城市', salary: '薪资' }
  const colors = { tfidf: 'var(--primary)', sbert: 'var(--purple)', skill: 'var(--green)', city: 'var(--orange)', salary: 'var(--red)' }
  return Object.entries(bd)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ key: k, label: labels[k] || k, value: v, color: colors[k] || 'var(--text-3)' }))
    .sort((a, b) => b.value - a.value)
}

// ---- 缺失技能 → 学习建议 ----
function learningSuggestions(missingKeywords) {
  if (!missingKeywords?.length) return []
  return missingKeywords.slice(0, 5).map(kw => {
    const lp = learningPaths[kw.toLowerCase()]
    return lp ? { ...lp, keyword: kw } : { title: kw, desc: '市场需求较高，建议掌握此项技能', icon: kw.slice(0, 4), keyword: kw }
  })
}

const engineLabel = computed(() => {
  if (!matchResult.value) return ''
  return matchResult.value.mode === 'dual_engine'
    ? 'TF-IDF + SBERT 双引擎'
    : 'TF-IDF 精确匹配'
})

// ---- 当前最佳匹配的技能缺口分析 ----
const topMatchGap = computed(() => {
  if (!matchResult.value?.top_matches?.length) return null
  const top = matchResult.value.top_matches[0]
  const required = top.required_skills || []
  const matched = top.reasons?.skill_match || []
  const missing = required.filter(s => !matched.includes(s.toLowerCase()))
  return { required, matched, missing: missing.slice(0, 8) }
})
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">岗位推荐</div>
      <div class="page-sub">TF-IDF + SBERT 双引擎智能匹配 — 了解为什么这些岗位适合你</div>
    </div>

    <!-- ===== 筛选区域 ===== -->
    <div class="filter-bar">
      <div class="skill-input-area">
        <input
          v-model="filters.skills"
          class="skill-input"
          placeholder="输入技能，逗号分隔（如 Python,Django,MySQL）"
          @keyup.enter="search"
        />
        <div class="quick-skills">
          <span v-for="q in quickSkills" :key="q.label" class="quick-tag"
            @click="fillSkills(q.skills)">{{ q.label }}</span>
        </div>
      </div>
      <div class="filter-row">
        <select v-model="filters.city" class="filter-select">
          <option value="">全部城市</option>
          <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
        </select>
        <input v-model.number="filters.salary_min" class="filter-input" type="number" placeholder="最低(K)" />
        <span class="range-sep">—</span>
        <input v-model.number="filters.salary_max" class="filter-input" type="number" placeholder="最高(K)" />
        <button class="filter-btn" @click="search" :disabled="loading">
          {{ loading ? '匹配中...' : '智能匹配' }}
        </button>
      </div>
    </div>

    <!-- ===== 匹配结果摘要 ===== -->
    <div v-if="matchResult" class="match-summary">
      <div class="summary-row">
        <div class="summary-item">
          <span class="sum-val">{{ matchResult.total_jobs_scanned.toLocaleString() }}</span>
          <span class="sum-label">扫描岗位</span>
        </div>
        <div class="summary-item">
          <span class="sum-val highlight">{{ matchResult.matched_count }}</span>
          <span class="sum-label">匹配成功</span>
        </div>
        <div class="summary-item">
          <span class="sum-val engine">{{ engineLabel }}</span>
          <span class="sum-label">匹配引擎</span>
        </div>
      </div>

      <!-- 关键词面板 -->
      <div v-if="matchResult.keyword_analysis" class="keyword-panel">
        <div class="kw-section">
          <div class="kw-title">你的技能画像</div>
          <div class="kw-tags">
            <span v-for="k in matchResult.keyword_analysis.critical_keywords" :key="k" class="kw-tag kw-has">{{ k }}</span>
          </div>
        </div>
        <div v-if="matchResult.keyword_analysis.missing_keywords?.length" class="kw-section">
          <div class="kw-title">市场高频但你还未掌握</div>
          <div class="kw-tags">
            <span v-for="k in matchResult.keyword_analysis.missing_keywords" :key="k" class="kw-tag kw-miss">{{ k }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 双栏布局：结果 + 学习建议 ===== -->
    <div class="result-layout" v-if="!loading && matchResult?.top_matches?.length">
      <!-- 左侧：匹配结果列表 -->
      <div class="result-list">
        <div class="result-item" v-for="(item, idx) in matchResult.top_matches" :key="item.job_id">
          <!-- 排名 + 岗位信息 -->
          <div class="ri-header">
            <div class="ri-rank" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</div>
            <div class="ri-info">
              <div class="ri-title">{{ item.title }}</div>
              <div class="ri-company">{{ item.company }}</div>
              <div class="ri-meta">
                <span v-if="item.city" class="ri-meta-tag">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                  {{ item.city }}
                </span>
                <span class="ri-meta-tag salary-tag">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                  {{ formatSalary(item) }}
                </span>
                <span class="ri-meta-tag" v-if="item.experience && item.experience !== 'None'">{{ item.experience }}</span>
                <span class="ri-meta-tag" v-if="item.education && item.education !== 'None'">{{ item.education }}</span>
              </div>
            </div>
            <!-- 综合评分 -->
            <div class="ri-score-block">
              <div class="ri-score" :style="{ color: scoreColor(item.score) }">{{ item.score }}</div>
              <div class="ri-score-label">综合分</div>
            </div>
          </div>

          <!-- 分项贡献度条形图 -->
          <div class="breakdown-bar" v-if="sortedBreakdown(item).length">
            <div class="breakdown-segment" v-for="seg in sortedBreakdown(item)" :key="seg.key"
              :style="{ width: (seg.value / item.score * 100) + '%', background: seg.color }"
              :title="seg.label + ': ' + seg.value + '分'"></div>
          </div>
          <div class="breakdown-legend" v-if="sortedBreakdown(item).length">
            <span class="bd-legend-item" v-for="seg in sortedBreakdown(item)" :key="seg.key">
              <span class="bd-dot" :style="{ background: seg.color }"></span>
              {{ seg.label }} {{ seg.value }}
            </span>
          </div>

          <!-- 匹配技能标签 -->
          <div class="ri-skills" v-if="item.reasons?.skill_match?.length">
            <span class="skill-tag" v-for="sk in item.reasons.skill_match" :key="sk">{{ sk }}</span>
            <span class="skill-coverage">覆盖率 {{ (item.reasons.skill_coverage * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <!-- 右侧：学习建议面板 -->
      <div class="side-panel">
        <!-- 技能缺口分析 -->
        <div class="panel-card" v-if="topMatchGap?.missing.length">
          <div class="panel-title">目标岗位技能缺口</div>
          <div class="panel-desc">以最佳匹配「{{ matchResult.top_matches[0].title }}」为参考</div>
          <div class="gap-list">
            <div class="gap-item" v-for="sk in topMatchGap.missing" :key="sk">
              <span class="gap-dot"></span>
              <span class="gap-name">{{ sk }}</span>
              <span class="gap-badge">需学习</span>
            </div>
          </div>
        </div>

        <!-- 学习路线建议 -->
        <div class="panel-card" v-if="learningSuggestions(matchResult.keyword_analysis?.missing_keywords).length">
          <div class="panel-title">学习路线建议</div>
          <div class="panel-desc">基于市场高频技能的进阶方向</div>
          <div class="learn-list">
            <div class="learn-item" v-for="lp in learningSuggestions(matchResult.keyword_analysis?.missing_keywords)" :key="lp.keyword">
              <div class="learn-icon">{{ lp.icon }}</div>
              <div class="learn-info">
                <div class="learn-title">{{ lp.title }}</div>
                <div class="learn-desc">{{ lp.desc }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 匹配原理说明 -->
        <div class="panel-card">
          <div class="panel-title">评分算法</div>
          <div class="algo-info">
            <div class="algo-row">
              <span class="algo-factor">关键词匹配</span>
              <span class="algo-weight">{{ matchResult.mode === 'dual_engine' ? '30%' : '50%' }}</span>
            </div>
            <div class="algo-row" v-if="matchResult.mode === 'dual_engine'">
              <span class="algo-factor">语义理解</span>
              <span class="algo-weight">30%</span>
            </div>
            <div class="algo-row">
              <span class="algo-factor">技能加权</span>
              <span class="algo-weight">{{ matchResult.mode === 'dual_engine' ? '20%' : '30%' }}</span>
            </div>
            <div class="algo-row">
              <span class="algo-factor">城市匹配</span>
              <span class="algo-weight">10%</span>
            </div>
            <div class="algo-row">
              <span class="algo-factor">薪资匹配</span>
              <span class="algo-weight">10%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 状态提示 ===== -->
    <div class="result-area" v-if="!matchResult?.top_matches?.length">
      <div v-if="!hasSearched" class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        </div>
        <span class="empty-title">输入你的技能，开始智能匹配</span>
        <span class="empty-hint">双引擎架构：TF-IDF 精确匹配 + SBERT 语义理解</span>
      </div>
      <div v-else-if="loading" class="empty-state">
        <div class="pulse-dot"></div>
        <span style="margin-top:16px">AI 正在分析技能并匹配岗位...</span>
      </div>
      <div v-else class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        </div>
        <span class="empty-title">没有找到匹配的岗位</span>
        <span class="empty-hint">尝试更换技能组合或放宽城市限制</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ===== 筛选栏 ===== */
.filter-bar {
  background: var(--bg-card); border-radius: var(--radius);
  padding: 20px; margin-bottom: 20px;
  box-shadow: var(--shadow); border: 1px solid var(--border);
}
.skill-input-area { margin-bottom: 14px; }
.skill-input {
  width: 100%; padding: 12px 16px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-page);
  color: var(--text-1); font-size: 15px; outline: none;
}
.skill-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }

.quick-skills { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.quick-tag {
  padding: 4px 12px; border-radius: 14px; font-size: 12px;
  background: var(--primary-soft); color: var(--primary);
  cursor: pointer; transition: all 0.2s; user-select: none;
  border: 1px solid transparent;
}
.quick-tag:hover { border-color: var(--primary); }

.filter-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.filter-select, .filter-input {
  padding: 9px 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-page);
  color: var(--text-1); font-size: 14px; outline: none;
}
.filter-select:focus, .filter-input:focus { border-color: var(--primary); }
.filter-input { width: 100px; }
.range-sep { color: var(--text-3); font-size: 13px; }
.filter-btn {
  padding: 10px 28px; border-radius: var(--radius-sm); border: none;
  background: var(--primary); color: var(--text-inverse); font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.filter-btn:hover:not(:disabled) { opacity: 0.9; }
.filter-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ===== 匹配摘要 ===== */
.match-summary { margin-bottom: 20px; }
.summary-row { display: flex; gap: 30px; margin-bottom: 16px; flex-wrap: wrap; }
.summary-item { display: flex; flex-direction: column; }
.sum-val { font-size: 18px; font-weight: 600; color: var(--text-1); }
.sum-val.highlight { color: var(--primary); }
.sum-val.engine { font-size: 13px; color: var(--green); }
.sum-label { font-size: 11px; color: var(--text-3); }

/* 关键词面板 */
.keyword-panel {
  display: flex; gap: 20px; flex-wrap: wrap;
  padding: 14px; background: var(--bg-card); border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}
.kw-section { flex: 1; min-width: 200px; }
.kw-title { font-size: 12px; font-weight: 600; color: var(--text-2); margin-bottom: 8px; }
.kw-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.kw-tag {
  padding: 3px 10px; border-radius: 10px; font-size: 12px;
}
.kw-tag.kw-has  { background: var(--green-soft); color: var(--green); }
.kw-tag.kw-miss { background: var(--red-soft);  color: var(--red); }

/* ===== 双栏布局 ===== */
.result-layout {
  display: grid; grid-template-columns: 1fr 320px; gap: 20px;
}

/* ===== 结果列表 ===== */
.result-list { display: flex; flex-direction: column; gap: 12px; }
.result-item {
  background: var(--bg-card); border-radius: var(--radius);
  padding: 20px 24px; box-shadow: var(--shadow);
  border: 1px solid transparent; transition: all 0.2s;
}
.result-item:hover {
  border-color: var(--primary-light);
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}

/* 头部行 */
.ri-header {
  display: flex; align-items: flex-start; gap: 14px; margin-bottom: 12px;
}
.ri-rank {
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; flex-shrink: 0;
  background: var(--bg-page); color: var(--text-3);
}
.ri-rank.rank-1 { background: var(--primary-soft); color: var(--primary); }
.ri-rank.rank-2 { background: var(--green-soft); color: var(--green); }
.ri-rank.rank-3 { background: var(--orange); color: var(--text-inverse); opacity: 0.8; }

.ri-info { flex: 1; min-width: 0; }
.ri-title { font-size: 15px; font-weight: 600; color: var(--text-1); margin-bottom: 2px; }
.ri-company { font-size: 13px; color: var(--text-3); margin-bottom: 6px; }
.ri-meta { display: flex; flex-wrap: wrap; gap: 10px; }
.ri-meta-tag {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text-3);
}
.ri-meta-tag svg { flex-shrink: 0; }
.ri-meta-tag.salary-tag { color: var(--primary); font-weight: 500; }

/* 综合评分 */
.ri-score-block {
  display: flex; flex-direction: column; align-items: center;
  min-width: 54px; flex-shrink: 0;
}
.ri-score {
  font-size: 28px; font-weight: 700; line-height: 1;
}
.ri-score-label { font-size: 10px; color: var(--text-3); margin-top: 2px; }

/* 分项贡献度条形图 */
.breakdown-bar {
  height: 6px; border-radius: 3px; background: var(--bg-page);
  display: flex; overflow: hidden; margin-bottom: 6px;
}
.breakdown-segment {
  height: 100%; transition: width 0.6s ease;
}
.breakdown-segment:first-child { border-radius: 3px 0 0 3px; }
.breakdown-segment:last-child { border-radius: 0 3px 3px 0; }

.breakdown-legend {
  display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 6px;
}
.bd-legend-item {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; color: var(--text-3);
}
.bd-dot { width: 8px; height: 8px; border-radius: 50%; }

/* 匹配技能 */
.ri-skills {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-top: 6px;
}
.skill-tag {
  padding: 2px 10px; border-radius: 10px; font-size: 11px;
  background: var(--green-soft); color: var(--green);
}
.skill-coverage {
  font-size: 11px; color: var(--text-3); margin-left: 4px;
}

/* ===== 右侧面板 ===== */
.side-panel { display: flex; flex-direction: column; gap: 14px; }
.panel-card {
  background: var(--bg-card); border-radius: var(--radius-sm);
  padding: 18px 20px; box-shadow: var(--shadow);
  border: 1px solid var(--border);
}
.panel-title { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.panel-desc { font-size: 11px; color: var(--text-3); margin-bottom: 12px; }

/* 技能缺口 */
.gap-list { display: flex; flex-direction: column; gap: 6px; }
.gap-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 6px;
  background: var(--bg-page); font-size: 13px;
}
.gap-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--red); }
.gap-name { flex: 1; color: var(--text-1); }
.gap-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 8px;
  background: var(--red-soft); color: var(--red);
}

/* 学习路线 */
.learn-list { display: flex; flex-direction: column; gap: 8px; }
.learn-item {
  display: flex; gap: 10px; padding: 10px 12px; border-radius: 8px;
  background: var(--bg-page); transition: all 0.15s;
}
.learn-item:hover { background: var(--primary-soft); }
.learn-icon {
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: var(--primary-soft); color: var(--primary);
  font-size: 10px; font-weight: 700; flex-shrink: 0;
}
.learn-info { min-width: 0; }
.learn-title { font-size: 13px; font-weight: 500; color: var(--text-1); }
.learn-desc { font-size: 11px; color: var(--text-3); margin-top: 2px; line-height: 1.5; }

/* 算法权重 */
.algo-info { display: flex; flex-direction: column; gap: 6px; }
.algo-row {
  display: flex; justify-content: space-between;
  padding: 4px 0; font-size: 12px;
}
.algo-factor { color: var(--text-2); }
.algo-weight { color: var(--primary); font-weight: 600; }

/* ===== 空状态 ===== */
.result-area { min-height: 300px; display: flex; align-items: center; justify-content: center; }
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  text-align: center; color: var(--text-3);
}
.empty-icon { margin-bottom: 12px; opacity: 0.5; color: var(--text-3); }
.empty-title { font-size: 15px; margin-bottom: 6px; }
.empty-hint { font-size: 12px; opacity: 0.7; }

.pulse-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: var(--primary); animation: pulse 1.2s infinite;
}
@keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1.2)} }

@media (max-width: 860px) {
  .result-layout { grid-template-columns: 1fr; }
  .side-panel { order: -1; }
}
</style>
