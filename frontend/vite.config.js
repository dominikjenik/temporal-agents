import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.js',
  },
  server: {
    open: true,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});