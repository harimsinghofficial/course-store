import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The FastAPI server serves the built files at /static/ (see main.py), so production URLs start with /static/.
// In `npm run dev` the app is served from "/" and API calls are proxied to FastAPI on :8000.
const API = process.env.API_URL || 'http://localhost:8000';

function proxyTo() {
  return {
    target: API,
    changeOrigin: true,
    // The backend's CSRF guard compares Origin with Host, so present the dev page as the backend's own origin.
    configure: (proxy) => proxy.on('proxyReq', (req) => req.setHeader('origin', API)),
  };
}

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/' : '/',
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    target: 'es2020',
    assetsInlineLimit: 0, // keep fonts as real files so they can be preloaded and cached
    chunkSizeWarningLimit: 350,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': proxyTo(),
      '/download': proxyTo(),
      '/admin/export': proxyTo(),
      '/favicon.svg': proxyTo(),
    },
  },
  test: { environment: 'node' },
}));
