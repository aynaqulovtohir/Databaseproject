import { expect, test } from './fixtures.ts'

import { EXAM_LAB_TITLE, storageState } from './accounts.ts'

test.describe('imtihon rejimi', () => {
  test.use({ storageState: storageState('student') })

  test("imtihon paytida banner ko'rinadi, AI kartalari yo'q, ball avtomatik", async ({ page }) => {
    await page.goto('/labs')
    await expect(page.getByText(/Imtihon davom etmoqda:/).first()).toBeVisible()
    await page.getByRole('link', { name: EXAM_LAB_TITLE }).first().click()

    await expect(page.getByText('Imtihon davom etmoqda', { exact: true })).toBeVisible()
    await expect(page.getByText(/AI yordami, murabbiy va o'zaro baholash o'chirilgan/)).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Murabbiy' })).toHaveCount(0)

    await page.getByLabel('SQL kod').fill('SELECT nomi FROM kitob;')
    await page.getByRole('button', { name: 'Baholashga topshirish' }).click()
    await expect(page.getByText("To'g'ri!")).toBeVisible()
    await expect(page.getByText(/Avtomatik/i).first()).toBeVisible()
  })
})
