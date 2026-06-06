// ============================================================
// useChart — ECharts 图表生命周期管理（Composition API）
// 替代重复的 echarts.init / setOption / resize / dispose 样板代码
// ============================================================
import { onUnmounted } from 'vue'
import * as echarts from 'echarts'

export function useChart() {
  // 当前图表实例
  let instance = null
  // ResizeObserver 实例（自动监听容器尺寸变化）
  let resizeObserver = null

  // ---- 初始化图表 ----
  function init(container) {
    // 支持传入元素 ID 字符串或 DOM 元素
    const el = typeof container === 'string'
      ? document.getElementById(container)
      : container

    if (!el) {
      console.warn('[useChart] 容器不存在:', container)
      return null
    }

    // 如果已有实例先销毁（避免重复 init）
    if (instance) dispose()

    instance = echarts.init(el)

    // 用 ResizeObserver 替代 window.resize（自动追踪、自动清理）
    resizeObserver = new ResizeObserver(() => {
      instance?.resize()
    })
    resizeObserver.observe(el)

    return instance
  }

  // ---- 设置/更新图表配置 ----
  function setOption(option) {
    if (!instance) return
    // notMerge=true：每次全量替换，避免 v-if 切换后旧配置残留
    instance.setOption(option, true)
  }

  // ---- 销毁图表 ----
  function dispose() {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    if (instance) {
      instance.dispose()
      instance = null
    }
  }

  // ---- 组件卸载时自动清理 ----
  onUnmounted(() => {
    dispose()
  })

  return { init, setOption, dispose }
}
