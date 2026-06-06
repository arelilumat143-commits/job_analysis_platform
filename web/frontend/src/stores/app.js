// ============================================================
// Pinia 全局状态 — 主题切换 + 数据缓存 + 图表联动
// ============================================================
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // ---- 主题 ----
  const theme = ref(localStorage.getItem('theme') || 'light')
  const isDark = computed(() => theme.value === 'dark')
  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    localStorage.setItem('theme', theme.value)
    applyTheme()
  }
  function applyTheme() {
    document.documentElement.className = theme.value === 'dark' ? 'dark' : ''
  }
  // 初始化主题
  applyTheme()

  // ---- 图表联动 — 选中城市 ----
  const selectedCity = ref('')
  function selectCity(city) {
    selectedCity.value = city
  }

  // ---- 全局加载 ----
  const loading = ref(false)

  // ---- 数据缓存（避免重复请求）----
  const statsCache = ref(null)
  const statsCacheTime = ref(0)
  const CACHE_TTL = 5 * 60 * 1000 // 5 分钟

  function isCacheValid(cacheTime) {
    return Date.now() - cacheTime < CACHE_TTL
  }

  return {
    theme, isDark, toggleTheme,
    selectedCity, selectCity,
    loading,
    statsCache, statsCacheTime, isCacheValid,
  }
})
