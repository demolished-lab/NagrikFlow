import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  if (mode === 'production' && !env.VITE_API_URL?.trim()) {
    throw new Error('VITE_API_URL is required for production builds; configure the public API origin or an explicit same-origin /api proxy.');
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // The Manus sandbox preview uses a generated *.manus.computer host.
      // This affects the dev server only; production builds are unchanged.
      allowedHosts: true,
      proxy: { '/api': { target: 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') } },
    },
  };
});
