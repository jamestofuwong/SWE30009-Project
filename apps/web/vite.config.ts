import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    // `npm run dev:api` serves the Hono worker on :8787
    proxy: { '/api': 'http://localhost:8787' },
  },
});
