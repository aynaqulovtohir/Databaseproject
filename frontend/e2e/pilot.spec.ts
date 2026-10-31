import type { Page } from '@playwright/test'

import { expect, test } from './fixtures.ts'

import { PILOT_ACCOUNTS, PILOT_LAB_TITLE, storageState } from './accounts.ts'
import { collectPageErrors, login } from './helpers.ts'

// Pilot: tajribaning butun yo'li foydalanuvchi ko'zi bilan. Talaba: rozilik → kirish testi → laboratoriya → chiqish testi →
// so'rovnoma. O'qituvchi: tahlil kartasi va eksport. Haqiqiy AI chaqirilmaydi: e2e muhitida kalitlar bo'sh.

async function takeQuiz(page: Page, title: RegExp, submit: 'Topshirish' | 'Yuborish') {
  await page.goto('/quizzes')
  await page.getByRole('link', { name: title }).click()
  await page.getByRole('button', { name: 'Boshlash' }).click()
  const questions = page.locator('fieldset')
  await expect(questions.first()).toBeVisible()
  for (const question of await questions.all()) await question.locator('input').first().check()
  await page.getByRole('button', { name: submit }).first().click()
  await page.getByRole('alertdialog').getByRole('button', { name: submit }).click()
  await expect(page.getByRole('alertdialog')).toHaveCount(0)
  await expect(questions).toHaveCount(0)
}

async function studentJourney(page: Page, username: string, survey: RegExp) {
  await login(page, username)
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Roziman' }).click()
  await expect(dialog).toBeHidden()

  await takeQuiz(page, /kirish testi/, 'Topshirish')

  await page.goto('/labs')
  await page.getByRole('link', { name: PILOT_LAB_TITLE }).first().click()
  await page.getByLabel('SQL kod').fill('SELECT nomi FROM kitob;')
  await page.getByRole('button', { name: 'Baholashga topshirish' }).click()
  await expect(page.getByText("To'g'ri!")).toBeVisible()

  await takeQuiz(page, /chiqish testi/, 'Topshirish')
  await takeQuiz(page, survey, 'Yuborish')
}

test.describe.serial('pilot: tajribaning butun yo\'li', () => {
  // Uchta test va laboratoriya bitta yo'lda: odatdagi 30 soniya yetmaydi
  test.setTimeout(120_000)

  // Login minutiga 5 marta bilan cheklangan (e2e/README.md): oldingi testlardagi loginlar hisobdan chiqishi kutiladi
  test.beforeAll(async () => {
    test.setTimeout(90_000)
    await new Promise((resolve) => setTimeout(resolve, 61_000))
  })

  test('tajriba guruhi talabasi', async ({ page }) => {
    const errors = collectPageErrors(page)
    await studentJourney(page, PILOT_ACCOUNTS.ai, /\(tajriba guruhi\)/)
    expect(errors).toEqual([])
  })

  test('nazorat guruhi talabasi: AI murabbiy yo\'q', async ({ page }) => {
    const errors = collectPageErrors(page)
    await studentJourney(page, PILOT_ACCOUNTS.control, /\(nazorat guruhi\)/)
    await page.goto('/labs')
    await page.getByRole('link', { name: PILOT_LAB_TITLE }).first().click()
    await expect(page.getByLabel('SQL kod')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Murabbiy' })).toHaveCount(0)
    expect(errors).toEqual([])
  })

  test.describe('o\'qituvchi', () => {
    test.use({ storageState: storageState('teacher') })

    test('tahlil kartasi to\'ladi, eksport yuklanadi', async ({ page }) => {
      const errors = collectPageErrors(page)
      await page.goto('/statistics')
      await expect(page.getByText('Aralashuvning bajarilishi: platformadagi AI dan foydalanish')).toBeVisible()
      await expect(page.getByText(/Tuzatilgan farq: .*95% CI \[/)).toBeVisible()
      await expect(page.getByText(/Tajriba: \d+ \/ \d+ talaba foydalangan/)).toBeVisible()
      await expect(page.getByText(/Guruhlar soni: tajriba 2, nazorat 2/)).toBeVisible()
      await expect(page.getByText("Sahifani ochib bo'lmadi")).toHaveCount(0)
      await expect(page.getByText('p = <')).toHaveCount(0)
      await page.screenshot({ path: 'test-results/pilot/statistika.png', fullPage: true })

      await page.goto('/labs')
      const download = page.waitForEvent('download')
      await page.getByRole('button', { name: "Tadqiqot ma'lumotlari" }).click()
      expect((await download).suggestedFilename()).toMatch(/^laboratoriya-tadqiqot-.*\.zip$/)
      await (await download).saveAs('test-results/pilot/eksport.zip')
      expect(errors).toEqual([])
    })
  })
})
