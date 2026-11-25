import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiProxy = {
  target: 'http://localhost:8000',
  bypass: (request: { headers: Record<string, string | string[] | undefined>; url?: string }) => {
    if (request.headers['sec-fetch-mode'] === 'navigate' && request.headers.accept?.includes('text/html')) {
      return request.url;
    }
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '^/(auth|search|predict|foods|restaurants|favorites|itinerary|articles|admin|health)(/|$)': apiProxy,
    },
  },
});
