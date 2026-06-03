<!-- ============================================================
 Sidebar — 持久化侧边栏（含主题切换 + 路由导航）
============================================================ -->
<script setup>
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../stores/app.js'

const router = useRouter()
const route = useRoute()
const store = useAppStore()

// 导航菜单项
const navItems = [
  { path: '/overview',  icon: '◉', label: '首页概览' },
  { path: '/salary',    icon: '◇', label: '薪资分析' },
  { path: '/skills',    icon: '○', label: '技能分析' },
  { path: '/recommend', icon: '□', label: '岗位推荐' },
  { path: '/data',      icon: '△', label: '数据管理' },
  { path: '/ai',        icon: '▽', label: 'AI智能报告' },
  { path: '/search',    icon: '🔍',label: '职位搜索' },
]

function isActive(path) {
  return route.path === path
}

function navigate(path) {
  router.push(path)
}
</script>

<template>
  <aside class="sidebar">
    <!-- Logo -->
    <div class="brand" @click="router.push('/')">
      <div class="name">招聘分析平台</div>
      <div class="sub">Job Analytics</div>
    </div>

    <!-- 数据库状态 -->
    <div class="db-badge">
      <span class="dot"></span>
      <span class="db-label">数据库</span>
      <span class="db-value">MYSQL</span>
    </div>

    <!-- 导航菜单 -->
    <div class="nav-label">导航</div>
    <div
      v-for="item in navItems"
      :key="item.path"
      class="nav-item"
      :class="{ active: isActive(item.path) }"
      @click="navigate(item.path)"
    >{{ item.icon }}  {{ item.label }}</div>

    <div class="nav-spacer"></div>

    <!-- 主题切换 -->
    <div class="theme-toggle" @click="store.toggleTheme()">
      <span class="theme-icon">{{ store.isDark ? '☀' : '🌙' }}</span>
      <span class="theme-label">{{ store.isDark ? '浅色模式' : '深色模式' }}</span>
    </div>

    <!-- 系统信息 -->
    <div class="nav-label">系统</div>
    <div class="sys-info">
      <div class="sys-row"><span>版本</span><span>v2.0</span></div>
      <div class="sys-row"><span>API</span><span>localhost:8000</span></div>
      <div class="sys-row"><span>数据库</span><span>job_analysis</span></div>
    </div>

    <div class="version">v2.0 · Vue Router + Pinia</div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 240px; min-width: 240px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  padding: 24px 0;
  display: flex; flex-direction: column;
  position: sticky; top: 0; height: 100vh;
  z-index: 10;
}
.brand { padding: 0 16px 20px 16px; margin-bottom: 8px; cursor: pointer; }
.brand .name { font-size: 17px; font-weight: 600; letter-spacing: 0.02em; color: var(--text-1); }
.brand .sub  { font-size: 12px; color: var(--text-3); margin-top: 4px; }

.db-badge {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 18px; margin: 0 12px 20px 12px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  box-shadow: var(--shadow); font-size: 12px;
}
.db-badge .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); }
.db-label { color: var(--text-3); }
.db-value { color: var(--text-1); font-weight: 500; margin-left: auto; }

.nav-label {
  font-size: 11px; color: var(--text-3);
  padding: 0 18px; margin: 0 0 4px 0;
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 500;
}
.nav-item {
  padding: 8px 16px; margin: 2px 8px; border-radius: 12px;
  font-size: 14px; color: var(--text-2);
  cursor: pointer; transition: all 0.2s; user-select: none;
}
.nav-item:hover  { background: rgba(91,141,239,0.06); }
.nav-item.active { background: var(--primary-soft); color: var(--primary); font-weight: 500; }

.nav-spacer { height: 24px; }

.theme-toggle {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 18px; margin: 0 12px 16px 12px;
  background: var(--bg-card); border-radius: var(--radius-sm);
  box-shadow: var(--shadow); cursor: pointer;
  transition: all 0.2s; font-size: 13px;
}
.theme-toggle:hover { box-shadow: var(--shadow-hover); }
.theme-icon  { font-size: 16px; }
.theme-label { color: var(--text-2); }

.sys-info { font-size: 12px; color: var(--text-3); padding: 0 18px; line-height: 2.2; margin-top: auto; }
.sys-row  { display: flex; justify-content: space-between; }
.sys-row span:last-child { color: var(--text-2); }
.version { padding: 12px 18px 0; font-size: 10px; color: var(--text-3); }

@media (max-width: 768px) {
  .sidebar { width: 100%; min-width: unset; height: auto; position: static; flex-direction: row; flex-wrap: wrap; padding: 12px; gap: 6px; align-items: center; }
  .brand { padding: 0; margin: 0; }
  .db-badge, .nav-label, .nav-spacer, .sys-info, .theme-toggle, .version { display: none; }
  .nav-item { font-size: 11px; padding: 5px 8px; margin: 0; }
}
</style>
