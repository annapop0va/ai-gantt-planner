import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const src = fileURLToPath(new URL('./src', import.meta.url))
// Canonical demo data lives at the repository root and is shared with backend/QA.
// It is aliased rather than copied so there is exactly one source of truth.
const fixtures = fileURLToPath(new URL('../fixtures', import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': src,
      '@fixtures': fixtures,
    },
  },
  server: {
    port: 5173,
    // Required because the fixtures directory sits outside the Vite root.
    fs: { allow: ['..'] },
  },
})
