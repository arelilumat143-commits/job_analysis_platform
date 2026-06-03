<!-- ============================================================
 Recommend — 岗位推荐页
 根据用户输入条件（城市/薪资/技能）推荐匹配职位
 数据来源：/api/jobs（带查询参数）
 ============================================================ -->
<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/app.js'
import { useApi } from '../composables/useApi.js'

const store = useAppStore()
const { get } = useApi()

const loading = ref(false)
const results = ref([])
const hasSearched = ref(false)

// 筛选条件
const filters = ref({
  city: '',
  salary_min: 0,
  keyword: '',
  limit: 10,
})

const cities = ['北京', '上海', '广州', '深圳', '杭州', '成都', '南京', '武汉', '西安', '郑州']

async function search() {
  loading.value = true
  hasSearched.value = true
  const params = {}
  if (filters.value.city) params.city = filters.value.city
  if (filters.value.salary_min > 0) params.salary_min = filters.value.salary_min
  if (filters.value.keyword) params.keyword = filters.value.keyword
  params.limit = filters.value.limit

  const d = await get('/api/jobs', params)
  if (d?.items) {
    results.value = d.items
  } else {
    results.value = []
  }
  loading.value = false
}

// 格式化薪资
function formatSalary(item) {
  if (!item.salary_min && !item.salary_max) return '面议'
  const min = item.salary_min ? item.salary_min + 'K' : ''
  const max = item.salary_max ? item.salary_max + 'K' : ''
  return min && max ? `${min} - ${max}` : (min || max)
}
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <div class="page-title">岗位推荐</div>
      <div class="page-sub">根据条件筛选推荐职位</div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="filters.city" class="filter-select">
        <option value="">全部城市</option>
        <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="filters.salary_min" class="filter-select">
        <option :value="0">最低薪资</option>
        <option :value="5">5K+</option>
        <option :value="10">10K+</option>
        <option :value="15">15K+</option>
        <option :value="20">20K+</option>
        <option :value="30">30K+</option>
      </select>
      <input v-model="filters.keyword" class="filter-input" placeholder="输入关键词（如 Java）" @keyup.enter="search" />
      <button class="filter-btn" @click="search" :disabled="loading">
        {{ loading ? '搜索中...' : '搜索' }}
      </button>
    </div>

    <!-- 结果列表 -->
    <div class="result-area">
      <div v-if="!hasSearched" class="empty-state">
        <span>请设置筛选条件后点击搜索</span>
        <span class="empty-hint">支持按城市、薪资、关键词组合筛选</span>
      </div>
      <div v-else-if="loading" class="empty-state">
        <span>搜索中...</span>
      </div>
      <div v-else-if="!results.length" class="empty-state">
        <span>未找到匹配职位</span>
        <span class="empty-hint">尝试放宽筛选条件</span>
      </div>
      <div v-else class="result-list">
        <div class="result-item" v-for="item in results" :key="item.id">
          <div class="ri-left">
            <div class="ri-title">{{ item.title }}</div>
            <div class="ri-company">{{ item.company }}</div>
            <div class="ri-meta">
              <span v-if="item.city">{{ item.city }}</span>
              <span v-if="item.experience">{{ item.experience }}</span>
              <span v-if="item.education">{{ item.education }}</span>
            </div>
          </div>
          <div class="ri-right">
            <div class="ri-salary">{{ formatSalary(item) }}</div>
            <div class="ri-source">{{ item.source === 'zhilian' ? '智联' : item.source }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap;
}
.filter-select, .filter-input {
  padding: 10px 16px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--bg-card);
  color: var(--text-1); font-size: 14px; outline: none;
}
.filter-select:focus, .filter-input:focus { border-color: var(--primary); }
.filter-input { width: 220px; }
.filter-btn {
  padding: 10px 24px; border-radius: var(--radius-sm); border: none;
  background: var(--primary); color: #fff; font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all 0.2s;
}
.filter-btn:hover:not(:disabled) { opacity: 0.9; }
.filter-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.result-area { min-height: 400px; }
.result-list { display: flex; flex-direction: column; gap: 10px; }
.result-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 24px; background: var(--bg-card); border-radius: var(--radius-sm);
  box-shadow: var(--shadow); transition: all 0.2s;
}
.result-item:hover { transform: translateX(4px); box-shadow: var(--shadow-hover); }
.ri-title   { font-size: 15px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.ri-company { font-size: 13px; color: var(--text-3); margin-bottom: 4px; }
.ri-meta    { display: flex; gap: 12px; font-size: 12px; color: var(--text-3); }
.ri-salary  { font-size: 16px; font-weight: 600; color: var(--primary); text-align: right; white-space: nowrap; }
.ri-source  { font-size: 11px; color: var(--text-3); text-align: right; margin-top: 2px; }
</style>
