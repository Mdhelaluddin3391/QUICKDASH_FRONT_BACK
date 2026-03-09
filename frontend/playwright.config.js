// frontend/playwright.config.js
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  timeout: 30000,
  testDir: './tests',
  use: {
    baseURL: 'http://localhost:8080',
    headless: true,
    viewport: { width: 1280, height: 720 },
  },
  webServer: {
    command: 'npm start',
    port: 8080,
    reuseExistingServer: true,
    timeout: 120000
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } }
  ]
});