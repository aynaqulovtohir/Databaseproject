import { test as base } from '@playwright/test'

export { expect } from '@playwright/test'

/**
 * Saqlangan sessiya bilan ishlaydigan testlar uchun.
 *
 * Refresh token har yangilanishda almashtiriladi, ishlatilgan nusxa qayta kelsa server barcha sessiyalarni yopadi
 * (backend/users/tokens.py). Shu sabab test tugagach yangi cookie e2e/.auth/ ga qayta yoziladi:
 * keyingi test eski nusxani emas, oxirgisini ishlatadi.
 */
export const test = base.extend<{ keepSession: void }>({
  keepSession: [
    async ({ context, storageState }, use) => {
      await use()
      if (typeof storageState !== 'string') return
      // Test tez tugasa, sahifa ochilishidagi refresh so'rovi yo'lda qoladi: server tokenni almashtirgan, faylga esa eski
      // cookie yoziladi. Keyingi test uni 30 soniyadan keyin yuborsa, server o'g'irlik deb hamma sessiyalarni yopadi
      for (const page of context.pages()) {
        await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => undefined)
      }
      await context.storageState({ path: storageState })
    },
    { auto: true },
  ],
})
