import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // 前端所有 /api 开头的请求，Vite 开发服务器帮忙转发给后端 8000
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true, // WebSocket（/api/v1/ws/...）也走代理转发
      },
    },
  },
})
