<!-- ============================================================
 MetricCard — 可复用的指标卡片组件
 功能：CountUp 数字动画 | Skeleton 加载态 | 悬浮动效
 Props:
   icon   — 图标文字（如 "◉"）
   value  — 指标数值（Number 会触发 CountUp，String 直接显示）
   label  — 底部说明文字
   loading — 是否显示骨架屏
   duration — 动画时长(ms)，默认 1500
============================================================ -->
<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  icon:     { type: String, default: '◉' },
  value:    { type: [Number, String], default: 0 },
  label:    { type: String, default: '' },
  loading:  { type: Boolean, default: false },
  duration: { type: Number, default: 1500 },
})

// 当前显示的数值（动画中间值）
const displayValue = ref(0)
// 是否字符串类型（直接显示，不动画）
const isString = typeof props.value === 'string'

// ---- CountUp 动画核心 ----
let animationId = null

function countUp(target) {
  // 取消上次动画
  if (animationId) cancelAnimationFrame(animationId)

  // 字符串直接显示
  if (typeof target === 'string') {
    displayValue.value = target
    return
  }

  const startValue = 0
  const startTime = performance.now()

  function update(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / props.duration, 1)
    // easeOutCubic — 先快后慢，视觉更自然
    const eased = 1 - Math.pow(1 - progress, 3)
    displayValue.value = Math.round(startValue + (target - startValue) * eased)

    if (progress < 1) {
      animationId = requestAnimationFrame(update)
    } else {
      displayValue.value = target // 确保最终值精确
    }
  }

  animationId = requestAnimationFrame(update)
}

// ---- 格式化显示值 ----
function formatted() {
  const v = displayValue.value
  if (typeof v === 'string') return v
  return v.toLocaleString()
}

// ---- 生命周期 ----
onMounted(() => {
  if (!props.loading) countUp(props.value)
})

// value 变化时重新动画
watch(() => props.value, (v) => {
  if (!props.loading) countUp(v)
})

// loading 结束后触发动画
watch(() => props.loading, (loading) => {
  if (!loading) countUp(props.value)
})

// 组件卸载时清理动画
onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
})
</script>

<template>
  <!-- 加载态：骨架屏 -->
  <div v-if="loading" class="metric-card skeleton">
    <div class="sk-icon"></div>
    <div class="sk-value"></div>
    <div class="sk-label"></div>
  </div>

  <!-- 正常态：带动画的指标 -->
  <div v-else class="metric-card">
    <div class="mc-icon">{{ icon }}</div>
    <div class="mc-value">{{ formatted() }}</div>
    <div class="mc-label">{{ label }}</div>
  </div>
</template>

<style scoped>
/* ---- 卡片基础 ----
   所有 padding / margin / radius 统一用这里的值，
   App.vue 不再单独写 .m-card 样式 */
.metric-card {
  background: var(--bg-card, #FFFFFF);
  border-radius: var(--radius, 16px);
  padding: 28px 24px;
  text-align: center;
  box-shadow: var(--shadow, 0 1px 3px rgba(0,0,0,0.04));
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  cursor: default;
}
.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover, 0 4px 12px rgba(0,0,0,0.08));
}

/* ---- 内容样式 ---- */
.mc-icon {
  font-size: 1.5rem;
  margin-bottom: 10px;
  opacity: 0.7;
  color: var(--primary, #5B8DEF);
}
.mc-value {
  font-size: 2.2rem;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: var(--text-1, #2C2C2C);
}
.mc-label {
  font-size: 0.82rem;
  color: var(--text-3, #A0A0A0);
  margin-top: 6px;
}

/* ---- 骨架屏 ----
   用 CSS 动画模拟内容占位，避免加载时页面跳动 */
.skeleton { pointer-events: none; }
.skeleton .sk-icon,
.skeleton .sk-value,
.skeleton .sk-label {
  background: linear-gradient(90deg, #F0F0F0 25%, #E8E8E8 50%, #F0F0F0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
  margin-left: auto;
  margin-right: auto;
}
.sk-icon  { width: 28px; height: 28px; margin-bottom: 10px; }
.sk-value { width: 80%; height: 36px; margin-bottom: 6px; }
.sk-label { width: 60%; height: 14px; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
