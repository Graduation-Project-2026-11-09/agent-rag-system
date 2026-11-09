import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: process.env.VITE_USE_POLLING ? { usePolling: true, interval: 300 } : undefined,
    // 本番では Caddy が /api を Flask に転送する。開発ではその役割を Vite が担う
    proxy: {
      '/api': process.env.VITE_API_PROXY ?? 'http://localhost:5000',
    },
  },
})
