import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  // All environment variables must be prefixed with VITE_ to be exposed to the browser.
  // VITE_API_BASE_URL is the only required env var for this app.
  envPrefix: 'VITE_',

  server: {
    host: true,
    port: 5173,
  },

  build: {
    // Output directory for `npm run build`
    outDir: 'dist',
    // Generate source maps for production error debugging (disable if bundle size is a concern)
    sourcemap: false,
    rollupOptions: {
      output: {
        // Split React vendor code into a separate chunk — maximises CDN cache hits
        // because the vendor chunk only changes when React updates (not on every deploy).
        manualChunks: {
          vendor: ['react', 'react-dom'],
        },
      },
    },
  },
});
