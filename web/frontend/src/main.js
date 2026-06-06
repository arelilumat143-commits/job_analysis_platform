// ============================================================
// Vue3 应用入口 — frontend-v2
// 引入 Vue Router + Pinia 状态管理
// ============================================================
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router/index.js'
import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
