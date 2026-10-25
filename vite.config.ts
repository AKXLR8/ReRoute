import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  optimizeDeps: {
    include: ['react-is'],
  },
  server: {
    proxy: mode === 'development' ? {
      '/v1': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
    } : undefined,
  },
}))
