import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      vue: 'vue/dist/vue.runtime.esm-bundler.js',
    },
  },
  preview: {
    proxy: {
      '/api': {
        target: 'http://localhost:6288',
        changeOrigin: true,
      },
    },
  },
  server: {
    port: 6289,
    proxy: {
      '/api': {
        target: 'http://localhost:6288',
        changeOrigin: true,
      },
    },
  },
})
