<!-- ============================================================
 JobSearch — 职位搜索页
 支持关键词/城市/经验/薪资范围筛选，分页展示结果
 数据来源：/api/jobs（带查询参数 + 分页）
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

// 筛选条件
const filters = ref({
  keyword: '',
  city: '',
  experience: '',
  salary_min: '',
  salary_max: '',
})

// 预设选项
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

// 当前页
const currentPage = ref(1)

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

function formatSalary(item) {
  if (!item.salary_min && !item.salary_max) return '面议'
  const min = item.salary_min ? item.salary_min + 'K' : ''
  const max = item.salary_max ? item.salary_max + 'K' : ''
  return min && max ? `${min}-${max}` : (min || max)
}

// 分页按钮
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

onMounted(() => search())
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">职位搜索</div>
      <div class="page-sub">共 {{ pagination.total.toLocaleString() }} 条职位 · 支持多条件筛选</div>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <input v-model="filters.keyword" class="sb-input" placeholder="搜索职位名称或公司..."
        @keyup.enter="search(1)" />
      <select v-model="filters.city" class="sb-select">
        <option value="">全部城市</option>
        <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="filters.experience" class="sb-select">
        <option value="">经验不限</option>
        <option v-for="e in experiences" :key="e" :value="e">{{ e }}</option>
      </select>
      <select v-model="filters.salary_min" class="sb-select" @change="search(1)">
        <option value="">薪资不限</option>
        <option v-for="r in salaryRanges" :key="r.label" :value="r.min"
          :disabled="!r.min && !r.max">
          {{ r.label }}
        </option>
      </select>
      <button class="sb-btn" @click="search(1)" :disabled="loading">
        {{ loading ? '搜索中' : '搜索' }}
      </button>
    </div>

    <!-- 结果表格 -->
    <div class="table-wrap">
      <div v-if="loading" class="empty-state"><span>搜索中...</span></div>
      <div v-else-if="!results.length" class="empty-state">
        <span>未找到匹配职位</span>
        <span class="empty-hint">尝试更换关键词或放宽条件</span>
      </div>
      <table v-else class="job-table">
        <thead>
          <tr>
            <th style="width:30%">职位名称</th>
            <th style="width:20%">公司</th>
            <th style="width:10%">城市</th>
            <th style="width:12%">薪资</th>
            <th style="width:10%">经验</th>
            <th style="width:10%">学历</th>
            <th style="width:8%">来源</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in results" :key="item.id" class="job-row">
            <td class="td-title">{{ item.title }}</td>
            <td>{{ item.company }}</td>
            <td>{{ item.city || '--' }}</td>
            <td class="td-salary">{{ formatSalary(item) }}</td>
            <td>{{ item.experience || '--' }}</td>
            <td>{{ item.education || '--' }}</td>
            <td class="td-source">{{ item.source === 'zhilian' ? '智联' : item.source || '--' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="pagination.total_pages > 1">
      <button class="page-btn" :disabled="currentPage <= 1" @click="search(currentPage - 1)">上一页</button>
      <button v-for="p in pages" :key="p" class="page-btn" :class="{ active: p === currentPage }"
        @click="search(p)">{{ p }}</button>
      <button class="page-btn" :disabled="currentPage >= pagination.total_pages" @click="search(currentPage + 1)">下一页</button>
      <span class="page-info">共 {{ pagination.total_pages }} 页 / {{ pagination.total }} 条</span>
    </div>
  </div>
</template>

<style scoped>
.search-bar { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
.sb-input { flex: 1; min-width: 200px; padding: 10px 16px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-card); color: var(--text-1); font-size: 14px; outline: none; }
.sb-input:focus { border-color: var(--primary); }
.sb-select { padding: 10px 14px; border-radius: var(--radius-sm); border: 1px solid var(--border); background: var(--bg-card); color: var(--text-1); font-size: 14px; outline: none; cursor: pointer; }
.sb-select:focus { border-color: var(--primary); }
.sb-btn { padding: 10px 24px; border-radius: var(--radius-sm); border: none; background: var(--primary); color: #fff; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s; white-space: nowrap; }
.sb-btn:hover:not(:disabled) { opacity: 0.9; }
.sb-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.table-wrap { background: var(--bg-card); border-radius: var(--radius); box-shadow: var(--shadow); overflow-x: auto; }
.job-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.job-table th { text-align: left; padding: 14px 16px; background: var(--bg-sidebar); color: var(--text-2); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap; }
.job-table td { padding: 13px 16px; border-top: 1px solid var(--border); color: var(--text-1); }
.job-row { transition: background 0.15s; cursor: default; }
.job-row:hover { background: var(--primary-soft); }
.td-title { font-weight: 500; }
.td-salary { color: var(--primary); font-weight: 500; white-space: nowrap; }
.td-source { color: var(--text-3); font-size: 12px; }

.pagination { display: flex; align-items: center; gap: 6px; margin-top: 20px; justify-content: center; flex-wrap: wrap; }
.page-btn { padding: 8px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-card); color: var(--text-2); font-size: 13px; cursor: pointer; transition: all 0.15s; }
.page-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.page-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.page-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.page-info { font-size: 12px; color: var(--text-3); margin-left: 12px; }
</style>
