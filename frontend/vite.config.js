import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        // 框架依赖单独分包：内容稳定，浏览器可长期缓存
        manualChunks: {
          vue: ['vue', 'vue-router'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/media': 'http://127.0.0.1:8080',
    },
  },
})
