import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// The chat board as ONE html file (script and styles inlined: the chat sandbox allows no outside address). Built into the backend,
// which serves it as the ui:// resource. `pnpm build:mcp`.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  publicDir: false,
  build: {
    outDir: '../backend/app/mcp/ui',
    emptyOutDir: true,
    rollupOptions: { input: 'board.html' },
  },
})
