import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxy = {
    '/api': {
      target: env.BACKEND_URL || 'http://127.0.0.1:5000',
      changeOrigin: true,
      configure: (proxyServer) => {
        proxyServer.on('proxyReq', (proxyReq, req) => {
          if (!req.headers['x-api-key'] && env.API_KEY) {
            proxyReq.setHeader('X-API-Key', env.API_KEY)
          }
        })
      },
    },
  }

  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 5173, proxy },
  }
})
