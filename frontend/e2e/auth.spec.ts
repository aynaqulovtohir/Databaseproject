import { expect, test } from '@playwright/test'

import { ACCOUNTS, storageState } from './accounts.ts'
import { login } from './helpers.ts'

test('noto\'g\'ri parol bilan kirib bo\'lmaydi', async ({ page }) => {
  await login(page, ACCOUNTS.student.username, 'notogri-parol')
  await expect(page.getByText("Login yoki parol noto'g'ri.")).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

test('kirmagan foydalanuvchi login sahifasiga yuboriladi', async ({ page }) => {
  await page.goto('/statistics')
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('button', { name: 'Kirish' })).toBeVisible()
})

test('yangi talabadan tadqiqotga rozilik so\'raladi va qaror saqlanadi', async ({ page }) => {
  await login(page, ACCOUNTS.newcomer.username)
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Roziman' }).click()
  await expect(dialog).toBeHidden()

  // Qaror serverda saqlangan: sahifa yangilanganda qayta so'ralmaydi
  await page.reload()
  await expect(page.getByRole('heading', { name: `Xush kelibsiz, ${ACCOUNTS.newcomer.name}` })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test.describe('kirgan talaba', () => {
  test.use({ storageState: storageState('student') })

  test('chiqqandan keyin sahifalar yopiladi', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Chiqish' }).click()
    await expect(page).toHaveURL(/\/login$/)

    await page.goto('/quizzes')
    await expect(page).toHaveURL(/\/login$/)
  })
})
