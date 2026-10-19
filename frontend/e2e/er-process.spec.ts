import { expect, test } from '@playwright/test'

import { ACCOUNTS, ER_LAB_TITLE, storageState } from './accounts.ts'

// Ikki qism tartib bilan ishlaydi (workers: 1): avval talaba chizadi, keyin o'qituvchi jarayonni ko'radi
test.describe('ER-diagramma chizish jarayoni', () => {
  test.describe('talaba', () => {
    test.use({ storageState: storageState('student') })

    test('chizgan holati muharrirdan chiqqanda yoziladi', async ({ page }) => {
      await page.goto('/labs')
      await page.getByRole('link', { name: new RegExp(ER_LAB_TITLE) }).first().click()
      await page.getByRole('button', { name: "Obyekt qo'shish" }).click()
      await page.getByLabel('Obyekt nomi').fill('Talaba')

      const saved = page.waitForResponse((response) => response.url().includes('/er-snapshot/'))
      await page.getByRole('link', { name: 'Virtual laboratoriya' }).first().click()
      expect((await saved).status()).toBe(204)
    })
  })

  test.describe("o'qituvchi", () => {
    test.use({ storageState: storageState('teacher') })

    test('talabaning jarayonini qayta ko\'radi', async ({ page }) => {
      await page.goto('/labs')
      await page.getByRole('link', { name: new RegExp(ER_LAB_TITLE) }).first().click()
      const row = page.getByRole('row', { name: new RegExp(ACCOUNTS.student.name) })
      await row.getByRole('button', { name: 'Jarayon' }).click()

      const dialog = page.getByRole('dialog')
      await expect(dialog.getByText('Strategiya:')).toBeVisible()
      // Oxirgi qadam: talaba yozgan nom diagrammada
      await expect(dialog.getByText('Talaba', { exact: true }).first()).toBeVisible()
      // Birinchi qadam (10 soniyalik yozuv nomni yozishdan oldin ham tushgan bo'lishi mumkin)
      await dialog.getByRole('slider').fill('0')
      await expect(dialog.getByText(/^Qadam 1 \//)).toBeVisible()
      await expect(dialog.getByText("Obyekt qo'shildi")).toBeVisible()
    })
  })
})
