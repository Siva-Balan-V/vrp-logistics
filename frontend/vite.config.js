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
      exclude: [
        'src/__tests__/**',
        'src/main.jsx',
        'src/context/**',
        'src/hooks/**',
        '**/*.test.{js,jsx}',
        '**/*.config.{js,jsx}',
      ],
      thresholds: {
        lines: 30,
        functions: 25,
        branches: 55,
        statements: 30,
      },
    },
  },
})
