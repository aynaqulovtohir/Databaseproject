// Ko'rinish sozlamalari (mavzu, yozuv o'lchami): faqat shu brauzerda saqlanadi, serverga yuborilmaydi.
// Dastlabki qiymatni public/theme-init.js qo'yadi: sahifa chizilishidan oldin ishlashi kerak.
import { useSyncExternalStore } from 'react'

export const THEMES = [
  { value: 'light', label: "Yorug'" },
  { value: 'dark', label: "Qorong'i" },
  { value: 'system', label: "Qurilma bo'yicha" },
  { value: 'violet', label: 'Binafsha' },
  { value: 'green', label: 'Yashil' },
  { value: 'wine', label: 'Bordo' },
] as const

export const TEXT_SIZES = [
  { value: 'md', label: 'Odatiy' },
  { value: 'lg', label: 'Katta' },
  { value: 'xl', label: 'Juda katta' },
  { value: 'xxl', label: 'Eng katta' },
] as const

export type Theme = (typeof THEMES)[number]['value']
export type TextSize = (typeof TEXT_SIZES)[number]['value']

const THEME_KEY = 'mb-theme'
const TEXT_SIZE_KEY = 'mb-text-size'
const root = document.documentElement
const systemDark = window.matchMedia('(prefers-color-scheme: dark)')
const listeners = new Set<() => void>()

function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Saqlash taqiqlangan (maxfiy oyna): sozlama shu sahifa ochiq turganida ishlaydi
  }
}

function notify() {
  listeners.forEach((listener) => listener())
}

function applyDark() {
  const theme = root.dataset.theme
  root.classList.toggle('dark', theme === 'dark' || (theme === 'system' && systemDark.matches))
  notify()
}

systemDark.addEventListener('change', applyDark)

export function setTheme(theme: Theme) {
  root.dataset.theme = theme
  save(THEME_KEY, theme)
  applyDark()
}

export function setTextSize(size: TextSize) {
  root.dataset.textSize = size
  save(TEXT_SIZE_KEY, size)
  notify()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useTheme() {
  return useSyncExternalStore(subscribe, () => root.dataset.theme as Theme)
}

export function useTextSize() {
  return useSyncExternalStore(subscribe, () => root.dataset.textSize as TextSize)
}

export function useIsDark() {
  return useSyncExternalStore(subscribe, () => root.classList.contains('dark'))
}
