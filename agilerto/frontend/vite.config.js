import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In dev, forward /api calls to the FastAPI backend.
    proxy: { '/api': 'http://127.0.0.1:8000', '/tiles': 'http://127.0.0.1:8000' },
    host: true, // reachable from phones on the same network
  },
})
