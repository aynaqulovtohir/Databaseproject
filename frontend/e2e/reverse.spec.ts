import { expect, test } from './fixtures.ts'

import { REVERSE_LAB_TITLE, storageState } from './accounts.ts'

test.describe('teskari loyihalash laboratoriyasi', () => {
  test.describe('talaba', () => {
    test.use({ storageState: storageState('student') })

    test('berilgan bazani ko\'radi va diagramma chizadi', async ({ page }) => {
      await page.goto('/labs')
      await page.getByRole('link', { name: REVERSE_LAB_TITLE }).first().click()
      await expect(page.getByRole('heading', { name: 'Berilgan baza' })).toBeVisible()
      await expect(page.getByText('CREATE TABLE kafedra', { exact: false }).first()).toBeVisible()
      await expect(page.getByRole('button', { name: "Obyekt qo'shish" })).toBeVisible()
    })
  })

  test.describe("o'qituvchi", () => {
    test.use({ storageState: storageState('teacher') })

    test('namuna bazadan avtomatik hosil qilingan', async ({ page }) => {
      await page.goto('/labs')
      await page.getByRole('link', { name: REVERSE_LAB_TITLE }).first().click()
      await expect(page.getByText('Berilgan bazadan avtomatik hosil qilingan.', { exact: false })).toBeVisible()
      await expect(page.getByText('oqituvchi', { exact: true }).first()).toBeVisible()
    })
  })
})
