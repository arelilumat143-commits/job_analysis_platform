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

@media (max-width: 768px) {
  .main { padding: 1rem; }
}
</style>
