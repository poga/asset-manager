import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/assets/',
  test: {
    environment: 'jsdom',
    globals: true,
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: ['dev.taileea02.ts.net'],
    proxy: {
      '/assets/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/assets/, '')
      }
    }
  }
})
