<!-- ============================================================
 ChartCard — 可复用的图表卡片容器
 功能：标题 | 图表插槽 | Skeleton 加载态 | 悬浮动效
 Props:
   title   — 图表标题
   loading — 是否显示骨架屏
 Slots:
   default — 图表内容区（放 ECharts 容器 div）
============================================================ -->
<script setup>
defineProps({
  title:   { type: String, default: '' },
  loading: { type: Boolean, default: false },
})
</script>

<template>
  <div class="chart-card">
    <!-- 标题栏 -->
    <h3 v-if="title" class="cc-title">{{ title }}</h3>

    <!-- 骨架屏 -->
    <div v-if="loading" class="cc-skeleton">
      <div class="sk-bar sk-bar-1"></div>
      <div class="sk-bar sk-bar-2"></div>
      <div class="sk-bar sk-bar-3"></div>
      <div class="sk-bar sk-bar-4"></div>
      <div class="sk-bar sk-bar-5"></div>
    </div>

    <!-- 图表内容插槽 -->
    <div v-else class="cc-body">
      <slot></slot>
    </div>
  </div>
</template>

<style scoped>
/* ---- 卡片基础 ----
   和 MetricCard 保持一致的设计语言 */
.chart-card {
  background: var(--bg-card, #FFFFFF);
  border-radius: var(--radius, 16px);
  padding: 28px 32px;
  box-shadow: var(--shadow, 0 1px 3px rgba(0,0,0,0.04));
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.chart-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover, 0 4px 12px rgba(0,0,0,0.08));
}

.cc-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-1, #2C2C2C);
}

/* 图表容器自动撑满 */
.cc-body {
  width: 100%;
}

/* ---- 骨架屏 ----
   模拟柱状图占位，5 根不同长度的条 */
.cc-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 20px 0;
}
.sk-bar {
  height: 16px;
  border-radius: 6px;
  background: linear-gradient(90deg, #F0F0F0 25%, #E8E8E8 50%, #F0F0F0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.sk-bar-1 { width: 90%; }
.sk-bar-2 { width: 75%; }
.sk-bar-3 { width: 60%; }
.sk-bar-4 { width: 80%; }
.sk-bar-5 { width: 50%; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ---- 响应式 ---- */
@media (max-width: 768px) {
  .chart-card {
    padding: 20px 16px;
  }
}
</style>
