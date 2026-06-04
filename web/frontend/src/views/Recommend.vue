<!-- ============================================================
 Recommend — 岗位推荐页（v2 双引擎智能匹配版）
 算法：TF-IDF（精确关键词）+ SBERT（语义理解）双引擎
 特性：关键词分析、缺失技能检测、分项评分展示
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

// ── 筛选条件 ──
const filters = ref({
  skills: 'Python,Django',
  city: '北京',
  salary_min: null,
  salary_max: null,
  top_n: 10,
})

// ── 常用配置 ──
const cities = ['北京', '上海', '广州', '深圳', '杭州', '成都', '南京', '武汉', '西安', '郑州']

// ── 技能快捷标签 ──
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

// ── 执行智能匹配 ──
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

// ── 快捷填充技能 ──
function fillSkills(skills) {
  filters.value.skills = skills
}

// ── 格式化薪资 ──
function formatSalary(item) {
  if (!item.salary_min && !item.salary_max) return '面议'
  const min = item.salary_min ? item.salary_min + 'K' : ''
  const max = item.salary_max ? item.salary_max + 'K' : ''
  return min && max ? `${min} - ${max}` : (min || max)
}

// ── 评分颜色编码 ──
function scoreColor(score) {
  if (score >= 70) return 'var(--green)'
  if (score >= 50) return 'var(--orange)'
  return 'var(--text-3)'
}

// ── 引擎模式显示 ──
const engineLabel = computed(() => {
  if (!matchResult.value) return ''
  return matchResult.value.mode === 'dual_engine'
    ? 'TF-IDF + SBERT 双引擎'
    : 'TF-IDF 精确匹配'
})
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">岗位推荐</div>
      <div class="page-sub">TF-IDF + SBERT 双引擎智能匹配，输入技能找出最合适的岗位</div>
    </div>

    <!-- ==================== 筛选条件 ==================== -->
    <div class="filter-bar">
      <div class="skill-input-area">
        <input
          v-model="filters.skills"
          class="skill-input"
          placeholder="输入技能，逗号分隔（如 Python,Django,MySQL）"
          @keyup.enter="search"
        />
        <div class="quick-skills">
          <span
            v-for="q in quickSkills" :key="q.label"
            class="quick-tag"
            @click="fillSkills(q.skills)"
          >{{ q.label }}</span>
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

    <!-- ==================== 匹配结果摘要 ==================== -->
    <div v-if="matchResult" class="match-summary">
      <div class="summary-row">
        <div class="summary-item">
          <span class="sum-val">{{ matchResult.total_jobs_scanned.toLocaleString() }}</span>
          <span class="sum-label">扫描岗位</span>
        </div>
        <div class="summary-item">
          <span class="sum-val">{{ matchResult.matched_count }}</span>
          <span class="sum-label">匹配成功</span>
        </div>
        <div class="summary-item">
          <span class="sum-val" style="font-size:13px">{{ engineLabel }}</span>
          <span class="sum-label">匹配引擎</span>
        </div>
        <div class="summary-item">
          <span class="sum-val" style="font-size:13px; max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            {{ matchResult.user_skills.filter(s => s.length <= 15).join(', ') }}
          </span>
          <span class="sum-label">匹配依据</span>
        </div>
      </div>

      <!-- 关键词分析面板 -->
      <div v-if="matchResult.keyword_analysis" class="keyword-panel">
        <div class="kw-section">
          <div class="kw-title">你的关键技能</div>
          <div class="kw-tags">
            <span v-for="k in matchResult.keyword_analysis.critical_keywords" :key="k" class="kw-tag kw-has">{{ k }}</span>
          </div>
        </div>
        <div v-if="matchResult.keyword_analysis.missing_keywords?.length" class="kw-section">
          <div class="kw-title">建议补充技能（市场高频但你缺少）</div>
          <div class="kw-tags">
            <span v-for="k in matchResult.keyword_analysis.missing_keywords" :key="k" class="kw-tag kw-miss">{{ k }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 结果区域 ==================== -->
    <div class="result-area">
      <!-- 空状态 -->
      <div v-if="!hasSearched" class="empty-state">
        <span>输入你的技能，开始智能匹配岗位</span>
        <span class="empty-hint">双引擎架构：TF-IDF 精确匹配 + SBERT 语义理解</span>
      </div>
      <!-- 加载中 -->
      <div v-else-if="loading" class="empty-state">
        <span>AI 正在分析技能并匹配岗位...</span>
      </div>
      <!-- 无结果 -->
      <div v-else-if="!matchResult?.top_matches?.length" class="empty-state">
        <span>没有找到匹配的岗位</span>
        <span class="empty-hint">尝试更换技能组合或放宽城市限制</span>
      </div>
      <!-- 结果列表 -->
      <div v-else class="result-list">
        <div class="result-item" v-for="item in matchResult.top_matches" :key="item.job_id">
          <!-- 左侧：岗位信息 -->
          <div class="ri-left">
            <div class="ri-title">{{ item.title }}</div>
            <div class="ri-company">{{ item.company }}</div>
            <div class="ri-meta">
              <span v-if="item.city">📍 {{ item.city }}</span>
              <span v-if="item.salary_min || item.salary_max">💰 {{ formatSalary(item) }}</span>
              <span>📋 {{ item.reasons?.skill_match?.length || 0 }} 项技能匹配</span>
              <span v-if="item.sbert_score != null">🧠 SBERT: {{ item.sbert_score }}%</span>
            </div>
            <!-- 匹配技能标签 -->
            <div v-if="item.reasons?.skill_match?.length" class="skill-tags">
              <span v-for="sk in item.reasons.skill_match" :key="sk" class="skill-tag">{{ sk }}</span>
            </div>
          </div>
          <!-- 右侧：评分 + 分项 -->
          <div class="ri-right">
            <div class="ri-score" :style="{ color: scoreColor(item.score) }">{{ item.score }}</div>
            <div class="ri-score-label">综合分</div>
            <div class="ri-badges">
              <span v-if="item.tfidf_score != null" class="badge badge-blue">TF-IDF {{ item.tfidf_score }}%</span>
              <span v-if="item.reasons?.city_match" class="badge badge-green">城市匹配</span>
              <span v-if="item.reasons?.salary_match" class="badge badge-orange">薪资合适</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── 筛选栏 ── */
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
.skill-input:focus { border-color: var(--primary); }

.quick-skills { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.quick-tag {
  padding: 4px 12px; border-radius: 14px; font-size: 12px;
  background: var(--primary-soft); color: var(--primary);
  cursor: pointer; transition: all 0.2s; user-select: none;
  border: 1px solid transparent;
}
.quick-tag:hover { border-color: var(--primary); opacity: 0.8; }

.filter-row {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
}
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
  background: var(--primary); color: #fff; font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.filter-btn:hover:not(:disabled) { opacity: 0.9; }
.filter-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── 匹配摘要 ── */
.match-summary { margin-bottom: 20px; }
.summary-row {
  display: flex; gap: 30px; margin-bottom: 16px; flex-wrap: wrap;
}
.summary-item { display: flex; flex-direction: column; }
.sum-val  { font-size: 18px; font-weight: 600; color: var(--text-1); }
.sum-label { font-size: 11px; color: var(--text-3); }

/* ── 关键词面板 ── */
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

/* ── 结果 ── */
.result-area { min-height: 400px; }
.result-list { display: flex; flex-direction: column; gap: 10px; }
.result-item {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 18px 24px; background: var(--bg-card); border-radius: var(--radius-sm);
  box-shadow: var(--shadow); transition: all 0.2s;
}
.result-item:hover { transform: translateX(4px); box-shadow: var(--shadow-hover); }
.ri-left  { flex: 1; min-width: 0; }
.ri-title { font-size: 15px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.ri-company { font-size: 13px; color: var(--text-3); margin-bottom: 6px; }
.ri-meta {
  display: flex; gap: 14px; font-size: 12px; color: var(--text-3);
  margin-bottom: 8px; flex-wrap: wrap;
}

.skill-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.skill-tag {
  padding: 2px 10px; border-radius: 10px; font-size: 11px;
  background: var(--green-soft); color: var(--green);
}

.ri-right {
  display: flex; flex-direction: column; align-items: center;
  min-width: 90px; margin-left: 16px;
}
.ri-score { font-size: 28px; font-weight: 700; line-height: 1; }
.ri-score-label { font-size: 10px; color: var(--text-3); margin-top: 2px; margin-bottom: 6px; }
.ri-badges { display: flex; flex-direction: column; gap: 4px; align-items: center; }
.badge {
  font-size: 10px; padding: 2px 8px; border-radius: 8px; white-space: nowrap;
}
.badge-green  { background: var(--green-soft); color: var(--green); }
.badge-orange { background: var(--primary-soft); color: var(--primary); }
.badge-blue   { background: var(--primary-soft); color: var(--primary); font-weight: 600; }

/* 空状态 */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 300px; color: var(--text-3); text-align: center;
}
.empty-state span { font-size: 15px; margin-bottom: 6px; }
.empty-hint { font-size: 12px !important; color: var(--text-3); opacity: 0.7; }
</style>
