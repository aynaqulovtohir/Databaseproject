import { expect, test } from './fixtures.ts'

import { INTEGRITY_LAB_TITLE, storageState } from './accounts.ts'

const SOLUTION = `ALTER TABLE kitob ALTER COLUMN nomi SET NOT NULL;
ALTER TABLE kitob ALTER COLUMN muallif SET NOT NULL;
ALTER TABLE kitob ADD UNIQUE (isbn);
ALTER TABLE kitob ADD CHECK (nusxalar >= 0);
ALTER TABLE kitob ADD CHECK (yil BETWEEN 1450 AND 2100);`

test.describe('yaxlitlik cheklovlari laboratoriyasi', () => {
  test.use({ storageState: storageState('student') })

  test('sinovlar natijasi ko\'rinadi, to\'liq cheklovlar hammasidan o\'tadi', async ({ page }) => {
    await page.goto('/labs')
    await page.getByRole('link', { name: INTEGRITY_LAB_TITLE }).first().click()
    await expect(page.getByRole('heading', { name: 'Cheklovlar sinovlari' })).toBeVisible()
    await expect(page.getByText('3 ta yashirin sinov bor')).toBeVisible()

    const code = page.getByLabel('SQL kod')
    const check = page.getByRole('button', { name: 'Tekshirish' })

    // Faqat bitta qoida: qolgan hujumlar o'tib ketadi
    await code.fill('ALTER TABLE kitob ALTER COLUMN nomi SET NOT NULL;')
    await check.click()
    await expect(page.getByText(/Sinovlar: \d+ \/ 11 o'tdi/)).toBeVisible()
    await expect(page.getByText("Kod xatosiz ishladi, lekin ba'zi sinovlar o'tmadi:")).toBeVisible()
    await expect(page.getByText("«Takror ISBN» — o'tib ketdi.")).toBeVisible()

    await code.fill(SOLUTION)
    await check.click()
    await expect(page.getByText("Sinovlar: 11 / 11 o'tdi")).toBeVisible()
    await expect(page.getByText("To'g'ri!")).toBeVisible()
  })
})
