import { defineConfig, devices } from '@playwright/test'

// Brauzer testlari konteynerda ishlaydi (docker-compose.e2e.yml): batafsil e2e/README.md
export default defineConfig({
  testDir: './e2e',
  // Testlar bitta bazani o'zgartiradi (test topshirish, rozilik): tartib bilan, bittadan
  workers: 1,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://127.0.0.1:4173',
    locale: 'uz-UZ',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // PW_CHANNEL=chrome: Playwright brauzeri o'rniga kompyuterdagi Google Chrome (mahalliy ishga tushirish)
    channel: process.env.PW_CHANNEL,
  },
  projects: [
    // Har bir rol uchun bir marta kiriladi (login minutiga 5 marta bilan cheklangan), sessiya qayta ishlatiladi
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
  ],
})
