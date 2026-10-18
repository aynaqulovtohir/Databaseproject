import { expect, test as setup } from '@playwright/test'

import { ACCOUNTS, storageState, type SavedRole } from './accounts.ts'
import { login } from './helpers.ts'

const ROLES: SavedRole[] = ['admin', 'teacher', 'student']

for (const role of ROLES) {
  setup(`${role} sifatida kirish`, async ({ page }) => {
    await login(page, ACCOUNTS[role].username)
    await expect(page.getByRole('heading', { name: `Xush kelibsiz, ${ACCOUNTS[role].name}` })).toBeVisible()
    // Refresh token httpOnly cookie'da: keyingi testlar shu sessiya bilan kiradi
    await page.context().storageState({ path: storageState(role) })
  })
}
