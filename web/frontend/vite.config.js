import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 手动分包：将大型依赖拆分为独立 chunk，提升缓存命中率
        manualChunks: {
          // ECharts 单独分包（~1000KB），页面首次加载不阻塞
          echarts: ['echarts'],
          // Vue 核心运行时
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
        },
      },
    },
  },
})
