import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // /api so'rovlari backend konteyneriga uzatiladi (brauzer uchun bitta manzil)
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://backend:8000',
        changeOrigin: false,
      },
    },
  },
  // vite preview faqat brauzer testlarida (docker-compose.e2e.yml): Playwright konteyneri shu nom bilan murojaat qiladi.
  // Ishchi serverda frontend'ni Caddy beradi, preview ishlatilmaydi
  preview: {
    allowedHosts: ['e2e-frontend'],
  },
})
