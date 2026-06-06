<!-- ============================================================
 JobSearch v2 — 职位搜索页（卡片式布局）
 参考：Boss直聘 / LinkedIn 卡片风格
 功能：热门关键词 / 卡片列表 / 薪资色标 / 技能标签 / 骨架屏
 数据来源：/api/jobs
 ============================================================ -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'

const store = useAppStore()
const { get } = useApi()

const loading = ref(false)
const results = ref([])
const pagination = ref({ total: 0, page: 1, page_size: 20, total_pages: 0 })

// ---- 筛选条件 ----
const filters = ref({
  keyword: '',
  city: '',
  experience: '',
  salary_min: '',
  salary_max: '',
})

// ---- 预设选项 ----
const cities = ['北京', '上海', '广州', '深圳', '杭州', '成都', '南京', '武汉', '西安', '郑州', '合肥', '天津', '长沙', '重庆', '青岛', '济南']
const experiences = ['应届生', '1-3年', '3-5年', '5-10年', '10年以上', '不限']
const salaryRanges = [
  { label: '不限', min: '', max: '' },
  { label: '5K以下', min: '', max: '5' },
  { label: '5-10K', min: '5', max: '10' },
  { label: '10-15K', min: '10', max: '15' },
  { label: '15-20K', min: '15', max: '20' },
  { label: '20-30K', min: '20', max: '30' },
  { label: '30K+', min: '30', max: '' },
]

// ---- 热门关键词 ----
const hotKeywords = ['AI', 'Python', 'Java', '前端', '数据分析', '算法', '产品经理', '架构师', 'Golang', '运维']

// ---- 当前页 ----
const currentPage = ref(1)

// ---- 搜索 ----
async function search(page = 1) {
  loading.value = true
  currentPage.value = page

  const params = { page, page_size: 20 }
  if (filters.value.keyword) params.keyword = filters.value.keyword
  if (filters.value.city) params.city = filters.value.city
  if (filters.value.experience) params.experience = filters.value.experience
  if (filters.value.salary_min) params.salary_min = filters.value.salary_min
  if (filters.value.salary_max) params.salary_max = filters.value.salary_max

  const d = await get('/api/jobs', params)
  if (d?.items) {
    results.value = d.items
    pagination.value = d.pagination
  } else {
    results.value = []
  }
  loading.value = false
}

// ---- 格式化薪资 ----
function formatSalary(item) {
  if (!item.salary_min && !item.salary_max) return '面议'
  const min = item.salary_min ? item.salary_min + 'K' : ''
  const max = item.salary_max ? item.salary_max + 'K' : ''
  return min && max ? min + '-' + max : (min || max)
}

// ---- 薪资色标（高薪/中等/一般/面议）----
function salaryLevel(item) {
  const avg = (item.salary_min + item.salary_max) / 2
  if (!avg) return 'low'
  if (avg >= 20) return 'high'
  if (avg >= 10) return 'mid'
  return 'low'
}

// ---- 解析技能标签 ----
function parseSkills(item) {
  if (!item.skills) return []
  if (Array.isArray(item.skills)) return item.skills.slice(0, 4)
  try {
    const parsed = JSON.parse(item.skills)
    return Array.isArray(parsed) ? parsed.slice(0, 4) : []
  } catch {
    return []
  }
}

// ---- 分页按钮 ----
const pages = computed(() => {
  const total = pagination.value.total_pages
  const cur = currentPage.value
  const range = []
  let start = Math.max(1, cur - 2)
  let end = Math.min(total, cur + 2)
  if (end - start < 4) {
    if (start === 1) end = Math.min(total, start + 4)
    else start = Math.max(1, end - 4)
  }
  for (let i = start; i <= end; i++) range.push(i)
  return range
})

// ---- 快速搜索关键词 ----
function quickSearch(kw) {
  filters.value.keyword = kw
  search(1)
}

onMounted(() => search())
</script>

<template>
  <div class="page">
    <!-- 页面标题 -->
    <div class="page-hero">
      <div class="page-title">职位搜索</div>
      <div class="page-sub">共 {{ pagination.total.toLocaleString() }} 条职位 · 支持多条件筛选</div>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <div class="sb-input-wrap">
        <svg class="sb-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
        </svg>
        <input v-model="filters.keyword" class="sb-input" placeholder="搜索职位名称或公司..."
          @keyup.enter="search(1)" />
      </div>
      <select v-model="filters.city" class="sb-select">
        <option value="">全部城市</option>
        <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="filters.experience" class="sb-select">
        <option value="">经验不限</option>
        <option v-for="e in experiences" :key="e" :value="e">{{ e }}</option>
      </select>
      <select v-model="filters.salary_min" class="sb-select">
        <option value="">薪资不限</option>
        <option v-for="r in salaryRanges" :key="r.label" :value="r.min"
          :disabled="!r.min && !r.max">
          {{ r.label }}
        </option>
      </select>
      <button class="sb-btn" @click="search(1)" :disabled="loading">
        {{ loading ? '搜索中...' : '搜索' }}
      </button>
    </div>

    <!-- 热门关键词 -->
    <div class="hot-tags">
      <span class="hot-label">热门搜索：</span>
      <button v-for="kw in hotKeywords" :key="kw" class="hot-tag"
        @click="quickSearch(kw)">{{ kw }}</button>
    </div>

    <!-- 骨架屏加载 -->
    <div class="card-list" v-if="loading">
      <div v-for="n in 5" :key="n" class="job-card skeleton-card">
        <div class="jc-main">
          <div class="sk-line sk-title"></div>
          <div class="sk-line sk-company"></div>
          <div class="sk-tags">
            <span class="sk-tag"></span>
            <span class="sk-tag"></span>
            <span class="sk-tag"></span>
          </div>
        </div>
        <div class="jc-salary">
          <div class="sk-line sk-salary"></div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-else-if="!loading && !results.length">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
        </svg>
      </div>
      <div class="empty-title">未找到匹配职位</div>
      <div class="empty-desc">尝试更换关键词或放宽筛选条件</div>
      <div class="empty-actions">
        <button class="empty-btn" @click="filters = { keyword: '', city: '', experience: '', salary_min: '', salary_max: '' }; search(1)">
          清除所有筛选
        </button>
      </div>
    </div>

    <!-- 职位卡片列表 -->
    <div class="card-list" v-else>
      <div class="job-card" v-for="item in results" :key="item.id">
        <div class="jc-main">
          <!-- 职位标题行 -->
          <div class="jc-title-row">
            <span class="jc-title">{{ item.title }}</span>
            <span class="jc-source" v-if="item.source === 'zhilian'">智联</span>
            <span class="jc-source" v-else-if="item.source">{{ item.source }}</span>
          </div>
          <!-- 公司名 -->
          <div class="jc-company">{{ item.company }}</div>
          <!-- 元信息标签 -->
          <div class="jc-meta">
            <span class="jc-meta-tag" v-if="item.city">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              {{ item.city }}
            </span>
            <span class="jc-meta-tag" v-if="item.experience">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              {{ item.experience }}
            </span>
            <span class="jc-meta-tag" v-if="item.education">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 3 3 6 3s6-1 6-3v-5"/></svg>
              {{ item.education }}
            </span>
          </div>
          <!-- 技能标签 -->
          <div class="jc-skills" v-if="parseSkills(item).length">
            <span class="jc-skill-tag" v-for="sk in parseSkills(item)" :key="sk">{{ sk }}</span>
          </div>
        </div>
        <!-- 薪资区域 -->
        <div class="jc-salary">
          <span class="jc-salary-num" :class="'salary-' + salaryLevel(item)">
            {{ formatSalary(item) }}
          </span>
          <span class="jc-salary-unit" v-if="item.salary_min || item.salary_max">/月</span>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="pagination.total_pages > 1">
      <button class="page-btn" :disabled="currentPage <= 1" @click="search(currentPage - 1)">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        上一页
      </button>
      <button v-for="p in pages" :key="p" class="page-btn" :class="{ active: p === currentPage }"
        @click="search(p)">{{ p }}</button>
      <button class="page-btn" :disabled="currentPage >= pagination.total_pages" @click="search(currentPage + 1)">
        下一页
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
      </button>
      <span class="page-info">共 {{ pagination.total_pages }} 页 / {{ pagination.total }} 条</span>
    </div>
  </div>
</template>

<style scoped>
/* ===== 搜索栏 ===== */
.search-bar {
  display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap;
}
.sb-input-wrap {
  flex: 1; min-width: 200px; position: relative;
  display: flex; align-items: center;
}
.sb-icon {
  position: absolute; left: 12px; color: var(--text-3); pointer-events: none;
}
.sb-input {
  width: 100%; padding: 10px 16px 10px 36px;
  border-radius: var(--radius-sm); border: 1px solid var(--border);
  background: var(--bg-card); color: var(--text-1); font-size: 14px;
  outline: none; transition: border-color 0.2s;
}
.sb-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
.sb-select {
  padding: 10px 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-card);
  color: var(--text-1); font-size: 14px; outline: none; cursor: pointer;
  transition: border-color 0.2s;
}
.sb-select:focus { border-color: var(--primary); }
.sb-btn {
  padding: 10px 28px; border-radius: var(--radius-sm); border: none;
  background: var(--primary); color: var(--text-inverse);
  font-size: 14px; font-weight: 500; cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.sb-btn:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); }
.sb-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ===== 热门关键词 ===== */
.hot-tags {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 20px; flex-wrap: wrap;
}
.hot-label {
  font-size: 12px; color: var(--text-3); font-weight: 500;
}
.hot-tag {
  padding: 4px 14px; border-radius: 20px;
  border: 1px solid var(--border); background: var(--bg-card);
  color: var(--text-2); font-size: 12px; cursor: pointer;
  transition: all 0.2s;
}
.hot-tag:hover {
  border-color: var(--primary); color: var(--primary);
  background: var(--primary-soft);
}

/* ===== 卡片列表 ===== */
.card-list {
  display: flex; flex-direction: column; gap: 12px;
}
.job-card {
  display: flex; align-items: flex-start; gap: 20px;
  background: var(--bg-card); border-radius: var(--radius);
  padding: 20px 24px; box-shadow: var(--shadow);
  border: 1px solid transparent;
  transition: all 0.2s; cursor: default;
}
.job-card:hover {
  border-color: var(--primary-light);
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  transform: translateY(-1px);
}
.jc-main { flex: 1; min-width: 0; }
.jc-title-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
}
.jc-title {
  font-size: 16px; font-weight: 600; color: var(--text-1);
}
.jc-source {
  font-size: 10px; padding: 2px 8px; border-radius: 4px;
  background: var(--primary-soft); color: var(--primary);
  font-weight: 500; flex-shrink: 0;
}
.jc-company {
  font-size: 14px; color: var(--text-2); margin-bottom: 10px;
}
.jc-meta {
  display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px;
}
.jc-meta-tag {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text-3);
}
.jc-meta-tag svg { flex-shrink: 0; }

/* 技能标签 */
.jc-skills {
  display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;
}
.jc-skill-tag {
  display: inline-block; padding: 3px 10px; border-radius: 6px;
  background: var(--green-soft); color: var(--green);
  font-size: 11px; font-weight: 500;
}

/* 薪资区域 */
.jc-salary {
  display: flex; align-items: baseline; gap: 4px;
  flex-shrink: 0; padding-left: 16px;
}
.jc-salary-num {
  font-size: 20px; font-weight: 700;
}
.jc-salary-num.salary-high { color: var(--red); }
.jc-salary-num.salary-mid  { color: var(--orange); }
.jc-salary-num.salary-low {
  color: var(--text-2); font-weight: 500; font-size: 16px;
}
.jc-salary-unit {
  font-size: 12px; color: var(--text-3);
}

/* ===== 骨架屏 ===== */
.skeleton-card {
  pointer-events: none;
}
.sk-line {
  height: 14px; border-radius: 7px; margin-bottom: 8px;
  background: linear-gradient(90deg, var(--skeleton-base) 25%, var(--skeleton-shine) 50%, var(--skeleton-base) 75%);
  background-size: 200% 100%; animation: shimmer 1.5s infinite;
}
.sk-title   { width: 55%; height: 18px; }
.sk-company  { width: 35%; }
.sk-salary   { width: 80px; height: 22px; }
.sk-tags     { display: flex; gap: 8px; margin-top: 6px; }
.sk-tag      { width: 50px; height: 22px; border-radius: 6px; background: var(--skeleton-base); }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ===== 空状态 ===== */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  padding: 60px 20px; text-align: center;
}
.empty-icon {
  color: var(--text-3); margin-bottom: 16px; opacity: 0.6;
}
.empty-title {
  font-size: 18px; font-weight: 600; color: var(--text-1); margin-bottom: 8px;
}
.empty-desc {
  font-size: 14px; color: var(--text-3); margin-bottom: 20px;
}
.empty-btn {
  padding: 10px 24px; border-radius: var(--radius-sm);
  border: 1px solid var(--primary); background: transparent;
  color: var(--primary); font-size: 14px; cursor: pointer;
  transition: all 0.2s;
}
.empty-btn:hover { background: var(--primary-soft); }

/* ===== 分页 ===== */
.pagination {
  display: flex; align-items: center; gap: 6px;
  margin-top: 24px; justify-content: center; flex-wrap: wrap;
}
.page-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 8px 14px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--bg-card);
  color: var(--text-2); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.page-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.page-btn.active {
  background: var(--primary); color: var(--text-inverse); border-color: var(--primary);
}
.page-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.page-info {
  font-size: 12px; color: var(--text-3); margin-left: 12px;
}

@media (max-width: 600px) {
  .job-card { flex-direction: column; }
  .jc-salary { padding-left: 0; padding-top: 12px; border-top: 1px solid var(--border); width: 100%; }
}
</style>
