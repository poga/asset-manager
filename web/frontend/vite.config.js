import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue({
    template: {
      compilerOptions: {
        isCustomElement: tag => tag === 'model-viewer'
      }
    }
  })],
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
        target: 'http://localhost:38471',
        rewrite: (path) => path.replace(/^\/assets/, '')
      }
    }
  }
})
