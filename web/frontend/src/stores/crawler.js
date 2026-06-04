// ============================================================
// Pinia 爬虫状态管理 — 跨页面持久化
// 状态/日志/轮询独立于组件生命周期，切换页面不丢失
// ============================================================
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useApi } from '../composables/useApi.js'

export const useCrawlerStore = defineStore('crawler', () => {
  const { get, post } = useApi()

  // ── 列表爬虫状态 ──
  const crawlRunning = ref(false)
  const crawlTaskId = ref(null)
  const crawlLogs = ref([])
  const crawlForm = ref({
    source: 'zhilian',
    city: '',
    keyword: '',
    pages: 3,
  })

  // ── 详情爬虫状态 ──
  const detailRunning = ref(false)
  const detailStats = ref({ total: 0, success: 0, updated: 0, failed: 0, skipped: 0 })
  const detailForm = ref({ city: '', limit: 50 })

  // ── 轮询句柄（存在 Store 中，不随组件销毁）──
  let _taskPollTimer = null
  let _detailPollTimer = null
  let _onDataRefresh = null  // 外部注册的数据刷新回调

  // ── 日志管理 ──
  function addLog(type, msg) {
    const time = new Date().toLocaleTimeString('zh-CN')
    crawlLogs.value.unshift({ type, msg, time })
    if (crawlLogs.value.length > 200) {
      crawlLogs.value = crawlLogs.value.slice(0, 200)
    }
  }

  function clearLogs() {
    crawlLogs.value = []
  }

  // ===================================================================
  // 列表爬虫
  // ===================================================================
  async function startCrawl() {
    if (crawlRunning.value) return
    crawlRunning.value = true
    addLog('info', `启动爬虫: ${crawlForm.value.source} ${crawlForm.value.city || '全国'} "${crawlForm.value.keyword || '无关键词'}"`)

    try {
      const res = await post('/api/crawler/start', {
        source: crawlForm.value.source,
        city: crawlForm.value.city || null,
        keyword: crawlForm.value.keyword || null,
        max_pages: crawlForm.value.pages || 1,
      })
      if (res) {
        crawlTaskId.value = res.task_id
        addLog('success', `任务创建成功 ID: ${res.task_id}`)
        _startTaskPolling()
      } else {
        addLog('error', '任务创建失败，请检查后端服务')
        crawlRunning.value = false
      }
    } catch (e) {
      addLog('error', `启动失败: ${e.message || '未知错误'}`)
      crawlRunning.value = false
    }
  }

  function stopCrawl() {
    crawlRunning.value = false
    _stopTaskPolling()
    addLog('warn', '爬虫已停止')
    // 注意：后端任务无法真正中断，这里只停止前端轮询
  }

  function _startTaskPolling() {
    _stopTaskPolling()  // 防止重复
    _taskPollTimer = setInterval(async () => {
      try {
        const cs = await get('/api/crawler/status')
        if (!cs) return

        const runningTask = cs.running_tasks?.find(t => t.task_id === crawlTaskId.value)
        if (!runningTask && crawlRunning.value) {
          // 任务不在运行列表中，说明已完成
          // 查一次详情确认
          const detail = await get(`/api/crawler/task/${crawlTaskId.value}`)
          if (detail) {
            const st = detail.status || 'completed'
            if (st === 'completed') {
              addLog('success', `爬取完成: ${detail.message || '--'}`)
            } else if (st === 'failed') {
              addLog('error', `爬取失败: ${detail.message || '--'}`)
            }
            // 新增数据时触发刷新
            if (detail.result?.added_count > 0 && _onDataRefresh) {
              _onDataRefresh()
            }
          }
          crawlRunning.value = false
          _stopTaskPolling()
        } else if (runningTask) {
          addLog('info', runningTask.message || '运行中...')
        }
      } catch {
        // 轮询间隔忽略网络抖动
      }
    }, 3000)
  }

  function _stopTaskPolling() {
    if (_taskPollTimer) {
      clearInterval(_taskPollTimer)
      _taskPollTimer = null
    }
  }

  // ===================================================================
  // 详情页爬虫
  // ===================================================================
  async function startDetailScrape() {
    if (detailRunning.value) return
    detailRunning.value = true
    addLog('info', `启动详情页爬虫: ${detailForm.value.city || '全部城市'} 限制${detailForm.value.limit}条`)
    try {
      const params = new URLSearchParams()
      if (detailForm.value.city) params.set('city', detailForm.value.city)
      params.set('limit', detailForm.value.limit)
      params.set('concurrency', '3')
      const res = await post('/api/crawler/detail-scrape?' + params.toString())
      if (res) {
        addLog('success', '详情页爬虫已启动')
        _startDetailPolling()
      } else {
        addLog('error', '启动失败')
        detailRunning.value = false
      }
    } catch (e) {
      addLog('error', `启动失败: ${e.message || ''}`)
      detailRunning.value = false
    }
  }

  async function stopDetailScrape() {
    try {
      await post('/api/crawler/detail-scrape/stop')
      addLog('warn', '详情页爬虫停止信号已发送')
    } catch {
      // ignore
    }
    detailRunning.value = false
    _stopDetailPolling()
  }

  function _startDetailPolling() {
    _stopDetailPolling()
    _detailPollTimer = setInterval(async () => {
      try {
        const res = await get('/api/crawler/detail-scrape/status')
        if (res) {
          detailRunning.value = res.running
          if (res.stats) detailStats.value = res.stats
          if (!res.running) {
            addLog('success', `详情爬取完成: 成功${res.stats?.success || 0} 更新${res.stats?.updated || 0}`)
            _stopDetailPolling()
            if (res.stats?.success > 0 && _onDataRefresh) {
              _onDataRefresh()
            }
          }
        }
      } catch {
        // ignore
      }
    }, 3000)
  }

  function _stopDetailPolling() {
    if (_detailPollTimer) {
      clearInterval(_detailPollTimer)
      _detailPollTimer = null
    }
  }

  // ===================================================================
  // 状态恢复 — 组件挂载时调用，检查是否有遗留运行中的任务
  // ===================================================================
  async function reconcileWithBackend() {
    try {
      const cs = await get('/api/crawler/status')
      if (!cs) return

      const hasRunning = cs.running_tasks && cs.running_tasks.length > 0
      if (hasRunning) {
        // 有运行中的任务，恢复轮询
        const task = cs.running_tasks[0]
        crawlTaskId.value = task.task_id
        crawlRunning.value = true
        addLog('info', `检测到遗留任务 ${task.task_id}，恢复监控`)
        _startTaskPolling()
      }

      // 检查详情爬虫状态
      const ds = await get('/api/crawler/detail-scrape/status')
      if (ds?.running) {
        detailRunning.value = true
        if (ds.stats) detailStats.value = ds.stats
        addLog('info', '检测到详情爬虫仍在运行，恢复监控')
        _startDetailPolling()
      }
    } catch {
      // ignore
    }
  }

  // ── 注册外部数据刷新回调（由页面组件调用）──
  function onDataRefresh(fn) {
    _onDataRefresh = fn
  }

  // ── 清理（唯一销毁时机：页面真正关闭）──
  function destroy() {
    _stopTaskPolling()
    _stopDetailPolling()
    _onDataRefresh = null
  }

  return {
    // 状态
    crawlRunning, crawlTaskId, crawlLogs, crawlForm,
    detailRunning, detailStats, detailForm,
    // 操作
    startCrawl, stopCrawl, addLog, clearLogs,
    startDetailScrape, stopDetailScrape,
    // 生命周期
    reconcileWithBackend, onDataRefresh, destroy,
  }
})
