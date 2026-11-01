import { expect, test } from './fixtures.ts'

import { STEPS_LAB_TITLE, storageState } from './accounts.ts'

test.describe('laboratoriyani bajarish tartibi', () => {
  test.use({ storageState: storageState('student') })

  test('hozirgi qadam urinish, to\'g\'ri javob va topshirishga qarab siljiydi', async ({ page }) => {
    await page.goto('/labs')
    await page.getByRole('link', { name: STEPS_LAB_TITLE }).click()

    const steps = page.locator('details', { hasText: 'Bajarish tartibi' })
    const current = steps.locator('li[aria-current="step"]')
    await expect(steps.getByText('0 / 4 qadam')).toBeVisible()
    await expect(current).toContainText('Topshiriqni tushuning')

    const code = page.getByLabel('SQL kod')
    await code.fill('SELECT id FROM kitob;')
    await page.getByRole('button', { name: 'Tekshirish' }).click()
    await expect(steps.getByText('2 / 4 qadam')).toBeVisible()
    await expect(current).toContainText('Tekshiring va tuzating')

    await code.fill('SELECT nomi FROM kitob;')
    await page.getByRole('button', { name: 'Tekshirish' }).click()
    await expect(steps.getByText('3 / 4 qadam')).toBeVisible()
    await expect(current).toContainText('Baholashga topshiring')

    await page.getByRole('button', { name: 'Baholashga topshirish' }).click()
    await expect(steps.getByText('4 / 4 qadam')).toBeVisible()
    await expect(current).toHaveCount(0)
    await expect(steps.getByText(/Hozirgi ballingiz: \d+ \/ 100/)).toBeVisible()

    // Hammasi bajarilgach, qayta ochilganda blok joy egallamasligi uchun yopiq turadi
    await page.reload()
    await expect(steps.getByText('4 / 4 qadam')).toBeVisible()
    await expect(steps.getByRole('heading', { name: 'Baholashga topshiring' })).toBeHidden()
  })
})
