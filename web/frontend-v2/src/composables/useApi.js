// ============================================================
// useApi — 后端 API 请求封装
// 用法：const { get, post } = useApi()
//       const data = await get('/api/jobs/stats')
// ============================================================
import { ref } from 'vue'

const BASE_URL = 'http://localhost:8000'  // FastAPI 后端地址

export function useApi() {
  const loading = ref(false)
  const error = ref(null)

  // 通用请求函数
  async function request(path, options = {}) {
    loading.value = true
    error.value = null
    try {
      const url = `${BASE_URL}${path}`
      const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const json = await res.json()
      // FastAPI 统一返回格式 { code, message, data }
      if (json.code && json.code !== 200) {
        throw new Error(json.message || '请求失败')
      }
      return json.data !== undefined ? json.data : json
    } catch (e) {
      error.value = e.message
      console.error('[useApi]', e.message)
      return null
    } finally {
      loading.value = false
    }
  }

  function get(path, params = {}) {
    const query = new URLSearchParams(params).toString()
    const url = query ? `${path}?${query}` : path
    return request(url)
  }

  function post(path, body = {}) {
    return request(path, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  return { loading, error, get, post }
}
