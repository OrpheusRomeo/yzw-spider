import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发时把 /api 转发给后端，打包之后前端由 FastAPI 直接托管
const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  // 打包产物用相对路径，挂在子目录下也能用
  base: './',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    // 容器里没有字体，警告一堆
    chunkSizeWarningLimit: 1500
  }
})
