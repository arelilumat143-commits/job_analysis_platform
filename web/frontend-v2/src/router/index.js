// ============================================================
// 路由配置 — Vue Router 4
// 7 个页面 + 布局持久化 + 过渡动画
// ============================================================
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('../layouts/DefaultLayout.vue'),
    children: [
      { path: '',             redirect: '/overview' },
      { path: 'overview',     component: () => import('../views/Overview.vue'),    meta: { title: '首页概览' } },
      { path: 'salary',       component: () => import('../views/Salary.vue'),      meta: { title: '薪资分析' } },
      { path: 'skills',       component: () => import('../views/Skills.vue'),      meta: { title: '技能分析' } },
      { path: 'recommend',    component: () => import('../views/Recommend.vue'),   meta: { title: '岗位推荐' } },
      { path: 'data',         component: () => import('../views/DataManage.vue'),  meta: { title: '数据管理' } },
      { path: 'ai',           component: () => import('../views/AiReport.vue'),    meta: { title: 'AI智能报告' } },
      { path: 'search',       component: () => import('../views/JobSearch.vue'),   meta: { title: '职位搜索' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局路由守卫 — 更新页面标题
router.afterEach((to) => {
  document.title = (to.meta.title || '招聘分析平台') + ' | Job Analytics'
})

export default router
