import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'
import { resolve } from 'path'

export default defineConfig(({ command, mode }) => {
  const isMcpApp = mode === 'mcp-app'

  return {
    plugins: [react(), ...(isMcpApp ? [viteSingleFile()] : [])],
    server: {
      port: 5173,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    build: isMcpApp ? {
      outDir: '../mcp_apps_ui',
      emptyOutDir: false,
      rollupOptions: {
        input: resolve(__dirname, process.env.MCP_APP_ENTRY || 'customer-confirm.html'),
        output: {
          entryFileNames: '[name].js',
          assetFileNames: '[name].[ext]'
        }
      }
    } : undefined
  }
})
