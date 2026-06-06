// ============================================================
// useChart — ECharts 生命周期管理（支持多实例）
// 用法：const { init, setOption } = useChart()
//       const chart = init('chart-id')      // 创建/获取指定ID的实例
//       setOption('chart-id', { ... })      // 设置配置
// 组件卸载时自动清理所有实例
// ============================================================
import { onUnmounted } from 'vue'
import * as echarts from 'echarts'

export function useChart() {
  // 多实例管理：Map<容器ID, { instance, observer }>
  const instances = new Map()

  // 初始化指定ID的图表（同一ID多次调用会先销毁旧实例）
  function init(container) {
    const id = typeof container === 'string' ? container : container?.id
    const el = typeof container === 'string'
      ? document.getElementById(container)
      : container

    if (!el) {
      console.warn('[useChart] 容器不存在:', id)
      return null
    }

    // 如果该ID已有实例，先销毁旧实例
    disposeOne(id)

    const instance = echarts.init(el)
    const observer = new ResizeObserver(() => instance?.resize())
    observer.observe(el)

    instances.set(id, { instance, observer })
    return instance
  }

  // 获取指定ID的实例
  function getInstance(id) {
    return instances.get(id)?.instance || null
  }

  // 设置指定ID图表的配置
  function setOption(id, option) {
    const entry = instances.get(id)
    if (!entry) {
      console.warn('[useChart] 实例不存在，请先 init:', id)
      return
    }
    entry.instance.setOption(option, true)
  }

  // 销毁单个实例
  function disposeOne(id) {
    const entry = instances.get(id)
    if (entry) {
      entry.observer?.disconnect()
      entry.instance?.dispose()
      instances.delete(id)
    }
  }

  // 销毁所有实例
  function disposeAll() {
    instances.forEach((entry) => {
      entry.observer?.disconnect()
      entry.instance?.dispose()
    })
    instances.clear()
  }

  // 组件卸载时清理所有
  onUnmounted(() => disposeAll())

	/** 读取 CSS 变量值（支持暗色模式自动切换） */
	function readCssVar(name) {
	  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
	}

	return { init, getInstance, setOption, disposeOne, disposeAll, readCssVar }

}
