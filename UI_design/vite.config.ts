import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync } from 'node:fs';
const ui = JSON.parse(
  readFileSync(new URL('./.cache/ui-build.json', import.meta.url), 'utf8').replace(/^\uFEFF/, ''),
);
const target = process.env.TOPIC16_UI_BACKEND || `http://127.0.0.1:${ui.Port}`;
export default defineConfig({
  plugins: [react()],
  root: '.',
  build: { outDir: 'dist', chunkSizeWarningLimit: 1400 },
  server: {
    host: '127.0.0.1',
    port: ui.DevPort,
    strictPort: true,
    proxy: {
      '/api': {
        target,
        changeOrigin: true,
        configure(proxy) {
          proxy.on('proxyReq', (req) => {
            req.setHeader('Origin', target);
          });
        },
      },
    },
  },
});
