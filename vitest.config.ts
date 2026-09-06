import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['apps/frontend/src/**/*.test.{ts,tsx}', 'packages/**/*.test.{ts,tsx}'],
  },
});
