<!-- ============================================================
 DefaultLayout — 持久化布局（侧边栏 + 主内容 + 路由过渡动画）
 所有页面通过 <router-view> 在此渲染
============================================================ -->
<script setup>
import Sidebar from '../components/Sidebar.vue'
</script>

<template>
  <Sidebar />
  <main class="main">
    <router-view v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </router-view>
  </main>
</template>

<style scoped>
.main {
  flex: 1; padding: 2rem 3rem 3rem 3rem; max-width: 1200px;
}

/* 通用页面样式（各视图复用） */
.page-hero {
  margin-bottom: 36px; padding-bottom: 24px;
  border-bottom: 1px solid var(--border);
}
.page-title  { font-size: 1.5rem; font-weight: 600; margin-bottom: 6px; letter-spacing: -0.01em; }
.page-sub    { font-size: 0.88rem; color: var(--text-3); }

.metrics-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px;
}
.chart-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;
}
.chart-grid.span { grid-template-columns: 1fr; }

.chart-box { width: 100%; }

.empty-state {
  text-align: center; color: var(--text-3); padding: 80px 0; font-size: 15px;
}
.empty-hint { font-size: 13px; margin-top: 8px; display: inline-block; }

@media (max-width: 768px) {
  .main { padding: 1rem; }
  .metrics-grid, .chart-grid { grid-template-columns: 1fr; }
}
</style>
