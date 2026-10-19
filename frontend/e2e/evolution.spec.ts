import { expect, test } from './fixtures.ts'

import { EVOLUTION_LAB_TITLE, storageState } from './accounts.ts'

const MIGRATION = `ALTER TABLE mijoz ADD COLUMN ism VARCHAR(50), ADD COLUMN familiya VARCHAR(50);
UPDATE mijoz SET ism = split_part(fio, ' ', 1), familiya = split_part(fio, ' ', 2);
ALTER TABLE mijoz ALTER COLUMN ism SET NOT NULL, ALTER COLUMN familiya SET NOT NULL;
ALTER TABLE mijoz DROP COLUMN fio;`

test.describe('sxemani rivojlantirish laboratoriyasi', () => {
  test.use({ storageState: storageState('student') })

  test("yangi so'rovlar natijasi ko'rinadi, to'g'ri migratsiya o'tadi", async ({ page }) => {
    await page.goto('/labs')
    await page.getByRole('link', { name: EVOLUTION_LAB_TITLE }).first().click()
    await expect(page.getByRole('heading', { name: "Tekshiruv so'rovlari" })).toBeVisible()

    const code = page.getByLabel('SQL kod')
    const check = page.getByRole('button', { name: 'Tekshirish' })

    // Ustunlar qo'shilgan, lekin ma'lumot ko'chirilmagan
    await code.fill('ALTER TABLE mijoz ADD COLUMN ism VARCHAR(50), ADD COLUMN familiya VARCHAR(50);')
    await check.click()
    await expect(page.getByText(/Tekshiruv so'rovlari: [01] \/ 2 ishladi/)).toBeVisible()
    await expect(page.getByText('Kod xatosiz bajarildi, lekin natija kutilganidan farq qiladi:')).toBeVisible()

    await code.fill(MIGRATION)
    await check.click()
    await expect(page.getByText("Tekshiruv so'rovlari: 2 / 2 ishladi")).toBeVisible()
    await expect(page.getByText("To'g'ri!")).toBeVisible()
  })
})
