import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: ['dev.taileea02.ts.net'],
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
