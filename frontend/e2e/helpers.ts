import { expect, type Page } from '@playwright/test'

import { PASSWORD } from './accounts.ts'

export async function login(page: Page, username: string, password = PASSWORD) {
  await page.goto('/login')
  await page.getByLabel('Login', { exact: true }).fill(username)
  await page.getByLabel('Parol', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Kirish' }).click()
}

/** Sahifada brauzer xatolari (ushlanmagan istisno) bo'lmasligini kuzatadi. */
export function collectPageErrors(page: Page) {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

/** Sahifa to'liq ochildi: sarlavha bor, 404 yoki "ochib bo'lmadi" xatosi yo'q. */
export async function expectPageOpened(page: Page) {
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByText('Bunday sahifa topilmadi')).toHaveCount(0)
  await expect(page.getByText("Sahifani ochib bo'lmadi")).toHaveCount(0)
}
