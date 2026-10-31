import { expect, test } from './fixtures.ts'

import { storageState } from './accounts.ts'

test.describe('ko\'rinish sozlamalari', () => {
  test.use({ storageState: storageState('student') })

  test('mavzu va yozuv o\'lchami saqlanadi, sahifa siljimaydi', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /Ko'rinish/ }).click()
    await page.getByRole('menuitemradio', { name: "Qorong'i" }).click()
    await page.getByRole('menuitemradio', { name: 'Eng katta' }).click()
    await page.keyboard.press('Escape')
    await page.reload()
    await expect(page.locator('html')).toHaveClass(/dark/)
    await expect(page.locator('html')).toHaveAttribute('data-text-size', 'xxl')
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe('24px')
    await page.setViewportSize({ width: 390, height: 800 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0)
  })

  test('ruxsat etilmagan saqlangan qiymat e\'tiborsiz qoldiriladi', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('mb-theme', '"><script>alert(1)</script>'))
    await page.goto('/')
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  })
})
