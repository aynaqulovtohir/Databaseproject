import { expect, test } from './fixtures.ts'

import { QUIZ_TITLE, storageState } from './accounts.ts'

test.describe('talaba testni topshiradi', () => {
  test.use({ storageState: storageState('student') })

  test('javob beradi, topshiradi va natijani ko\'radi', async ({ page }) => {
    await page.goto('/quizzes')
    await page.getByRole('link', { name: new RegExp(QUIZ_TITLE) }).click()
    await expect(page.getByRole('heading', { level: 1, name: QUIZ_TITLE })).toBeVisible()

    await page.getByRole('button', { name: 'Boshlash' }).click()
    await page.getByRole('radio', { name: '3NF' }).check()
    await page.getByRole('radio', { name: "Yo'q" }).check()
    await expect(page.getByText('2 / 2 savolga javob berildi')).toBeVisible()

    await page.getByRole('button', { name: 'Topshirish' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Topshirish' }).click()

    await expect(page.getByText('Natijangiz')).toBeVisible()
    await expect(page.getByText('100%')).toBeVisible()
    await expect(page.getByText('2 / 2 ball')).toBeVisible()

    // Natija saqlangan: qayta ochilganda test yana boshlanmaydi
    await page.reload()
    await expect(page.getByText('Natijangiz')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Boshlash' })).toHaveCount(0)
  })
})
