import { expect, test } from './fixtures.ts'

import { storageState, type SavedRole } from './accounts.ts'
import { collectPageErrors, expectPageOpened } from './helpers.ts'

// Menyudagi har bir sahifa (har biri alohida yuklanadigan bo'lak) ochiladi
const MENUS: Record<SavedRole, string[]> = {
  admin: [
    'Foydalanuvchilar', 'Guruhlar', 'Materiallar', 'Topshiriqlar', 'Virtual laboratoriya', 'Testlar',
    'Statistika', 'Kompetentlik', 'Erta ogohlantirish', 'AI sifati', "Ko'r baholash", 'AI xarajati', 'Profil',
  ],
  teacher: [
    'Materiallar', 'Topshiriqlar', 'Virtual laboratoriya', 'Testlar',
    'Statistika', 'Kompetentlik', 'Erta ogohlantirish', 'AI sifati', "Ko'r baholash", 'Profil',
  ],
  student: ['Materiallar', 'Topshiriqlar', 'Virtual laboratoriya', 'Testlar', 'Profil'],
}

for (const role of Object.keys(MENUS) as SavedRole[]) {
  test.describe(role, () => {
    test.use({ storageState: storageState(role) })

    test('menyudagi barcha sahifalar ochiladi', async ({ page }) => {
      const errors = collectPageErrors(page)
      await page.goto('/')
      await expectPageOpened(page)

      const menu = page.getByRole('navigation', { name: 'Asosiy menyu' })
      for (const label of MENUS[role]) {
        await menu.getByRole('link', { name: label, exact: true }).click()
        await expect(menu.getByRole('link', { name: label, exact: true })).toHaveAttribute('aria-current', 'page')
        await expectPageOpened(page)
      }
      // Menyuda boshqa rolning sahifalari ko'rinmaydi
      await expect(menu.getByRole('link')).toHaveCount(MENUS[role].length + 1)
      expect(errors).toEqual([])
    })
  })
}

test.describe('talaba ruxsati', () => {
  test.use({ storageState: storageState('student') })

  for (const path of ['/statistics', '/users', '/risk']) {
    test(`${path} talabaga ochilmaydi`, async ({ page }) => {
      await page.goto(path)
      await expect(page.getByText('Bunday sahifa topilmadi')).toBeVisible()
    })
  }
})

test('noto\'g\'ri ekspert havolasi xabar beradi', async ({ page }) => {
  await page.goto('/expert/notogri-havola-tokeni-1234567890')
  await expect(page.getByText("Havola noto'g'ri yoki bekor qilingan.")).toBeVisible()
})
