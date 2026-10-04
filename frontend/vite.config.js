import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/docs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/redoc': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/__tests__/setup.js',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'html'],
      reportsDirectory: './coverage',
      // Vitest 3 dropped the old `coverage.all` default. Without an explicit
      // include, only files imported during the test run are reported, which
      // silently shrank the report from 23 files to 9 and flattered every
      // percentage. Keep this in sync with `exclude` below.
      include: ['src/**/*.{js,jsx}'],
      exclude: [
        'src/__tests__/**',
        'src/main.jsx',
        'src/context/**',
        'src/hooks/**',
        '**/*.test.{js,jsx}',
        '**/*.config.{js,jsx}',
      ],
      thresholds: {
        // Re-based on the @vitest/coverage-v8 5 measurement, NOT comparable to
        // the coverage-v8 2 numbers these replaced: v2 counted 260 branches
        // across src/ where v5 counts 949, so the old 55% branch floor was
        // measuring a much smaller branch set. Real coverage of src/ is
        // ~23-27%; the previous 33%/59% was partly a provider artifact.
        //
        // These must ratchet up, never down (docs/CI_PIPELINE_PLAN.md:261).
        // Raised from 21/20/25/21 by restoring src/__tests__/api.test.js.
        lines: 23,
        functions: 22,
        branches: 26,
        statements: 23,
      },
    },
  },
})
