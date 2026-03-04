import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // Tauri dev server 설정
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
  },

  // 빌드 설정
  build: {
    outDir: 'dist',
    // Tauri를 위한 소스맵 설정
    sourcemap: !!process.env.TAURI_DEBUG,
    // Tauri 개발 시 에러 추적을 위해 minify 설정
    minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
  },

  // 환경 변수 설정
  envPrefix: ['VITE_', 'TAURI_'],
})
