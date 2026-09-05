// Unit-test config for the v2 frontend. Deliberately separate from vite.config.js
// so the app build is untouched: `npm run build` never loads this file.
//
// Run it with `bash v2-testing/tools/fe-test.sh` (Node lives only in Docker here).
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// TZ is pinned to UTC because time.js's `whenShort` reads a Date with LOCAL
// getters — the same instant renders as a different day/hour in another zone, so
// the assertions would be machine-dependent otherwise. fe-test.sh also passes
// `-e TZ=UTC` to the container, which is what actually reaches the test workers;
// this line covers a direct `npx vitest run` in an already-UTC-less shell.
process.env.TZ = 'UTC'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/__tests__/**/*.test.{js,jsx}'],
    // CSS imports (ui.jsx pulls theme.css) resolve to an empty module — the
    // tests assert logic, never computed style.
    css: false,
    clearMocks: true,
  },
})
