import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { build as esbuildBuild } from 'esbuild';

/**
 * Compile the mobile service worker (`src/mobile/sw/serviceWorker.ts`) to
 * `dist/mobile/sw.js`.
 *
 * It MUST land at the build root (not under `assets/`) so the SW scope is
 * `./` from the served HTML — the registration call in
 * `src/mobile/sw/register.ts` uses `navigator.serviceWorker.register('./sw.js')`.
 */
function mobileServiceWorkerPlugin(): Plugin {
  return {
    name: 'ds-agent-mobile-sw',
    apply: 'build',
    async closeBundle() {
      const entry = path.resolve(__dirname, 'src/mobile/sw/serviceWorker.ts');
      const out = path.resolve(__dirname, 'dist/mobile/sw.js');
      await esbuildBuild({
        entryPoints: [entry],
        outfile: out,
        bundle: true,
        format: 'iife',
        target: 'es2020',
        platform: 'browser',
        minify: true,
        sourcemap: false,
        logLevel: 'warning',
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), mobileServiceWorkerPlugin()],
  root: 'src/mobile',
  base: './',
  publicDir: path.resolve(__dirname, 'public'),
  build: {
    outDir: '../../dist/mobile',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src/renderer'),
    },
  },
  server: {
    port: 5174,
  },
});
