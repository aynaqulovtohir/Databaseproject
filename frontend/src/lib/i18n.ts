// Interfeys tili: o'zbekcha (asosiy), inglizcha, ruscha. Tanlov faqat shu brauzerda saqlanadi.
//
// Matnlar koddagi o'zbekcha asl ko'rinishi bilan yoziladi: t("Bosh sahifa"). Tarjima lug'atlari
// (src/locales/en.ts, ru.ts) shu asl matnni kalit qilib oladi. Tarjimasi yo'q matn o'zbekcha qoladi,
// shuning uchun yangi matn qo'shilganda sahifa buzilmaydi. Lug'atlar faqat tanlanganda yuklanadi:
// o'zbekcha foydalanuvchi ortiqcha kod yuklamaydi.
//
// Til almashganda main.tsx ilovani qayta chizadi (key={lang}), shuning uchun komponentlar t() ni
// oddiy funksiya sifatida chaqiraveradi, alohida hook kerak emas.
import { useSyncExternalStore } from 'react'

export const LANGS = [
  { value: 'uz', label: "O'zbekcha", short: 'UZ', intl: 'uz-Latn-UZ' },
  { value: 'en', label: 'English', short: 'EN', intl: 'en-GB' },
  { value: 'ru', label: 'Русский', short: 'RU', intl: 'ru-RU' },
] as const

export type Lang = (typeof LANGS)[number]['value']
type Dictionary = Record<string, string>

const LANG_KEY = 'mb-lang'
const root = document.documentElement
const listeners = new Set<() => void>()
const loaders: Record<Exclude<Lang, 'uz'>, () => Promise<{ default: Dictionary }>> = {
  en: () => import('@/locales/en'),
  ru: () => import('@/locales/ru'),
}

const CONTEXT = '@@'

let current: Lang = 'uz'
let dictionary: Dictionary = {}

function isLang(value: unknown): value is Lang {
  return LANGS.some((item) => item.value === value)
}

function readSaved(): Lang {
  try {
    const value = localStorage.getItem(LANG_KEY)
    return isLang(value) ? value : 'uz'
  } catch {
    return 'uz'
  }
}

function apply(lang: Lang, dict: Dictionary) {
  current = lang
  dictionary = dict
  root.lang = lang
  listeners.forEach((listener) => listener())
}

async function load(lang: Lang): Promise<Dictionary> {
  if (lang === 'uz') return {}
  return (await loaders[lang]()).default
}

/** Tilni almashtiradi: lug'at yuklangach butun interfeys yangi tilda qayta chiziladi. */
export async function setLang(lang: Lang) {
  if (!isLang(lang)) return
  try {
    localStorage.setItem(LANG_KEY, lang)
  } catch {
    // Saqlash taqiqlangan (maxfiy oyna): tanlov shu sahifa ochiq turganida ishlaydi
  }
  apply(lang, await load(lang))
}

/** Ilova chizilishidan oldin saqlangan tilni yuklaydi (main.tsx). Lug'at yuklanmasa o'zbekcha qoladi. */
export async function initLang() {
  const lang = readSaved()
  if (lang === 'uz') return
  try {
    apply(lang, await load(lang))
  } catch {
    apply('uz', {})
  }
}

export function getLang(): Lang {
  return current
}

/** Intl uchun joriy til kodi (sana, son formatlari). */
export function intlLocale(): string {
  return LANGS.find((item) => item.value === current)!.intl
}

/**
 * Matnni joriy tilga o'giradi. {nomi} ko'rinishidagi o'rinlar params bilan to'ldiriladi:
 * t("Sizda {count} ta bildirishnoma bor", { count: 3 }). Natija React orqali oddiy matn
 * sifatida chiqadi (HTML sifatida emas), shuning uchun params xavfsiz.
 */
export function t(text: string, params?: Record<string, string | number | null | undefined>): string {
  // hasOwn: "constructor" kabi matnlar Object prototipidan qiymat olmasin.
  // "Kirish@@tugma": @@ dan keyingi qism faqat ma'noni ajratadi (kirish testi / tizimga kirish), ko'rsatilmaydi.
  const template = (Object.hasOwn(dictionary, text) && dictionary[text]) || text.split(CONTEXT)[0]
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name] ?? '') : match,
  )
}

/**
 * Modul darajasidagi yorliqlar lug'ati (masalan, ROLE_LABELS) uchun: qiymat har safar o'qilganda
 * joriy tilga o'giriladi. Modul bir marta yuklanadi, til esa keyin almashishi mumkin.
 */
const LOCALIZED_SKIP = new Set(['value', 'key', 'id', 'to', 'className', 'kind', 'tone'])
const proxies = new WeakMap<object, object>()

/**
 * Modul darajasidagi yorliqlar (masalan, ROLE_LABELS yoki [{ value, label }] ro'yxati) uchun: matn har
 * safar o'qilganda joriy tilga o'giriladi. Modul bir marta yuklanadi, til esa keyin almashishi mumkin.
 * Ichma-ich obyekt va massivlar ham o'giriladi; value/key/className kabi texnik maydonlar o'zgarmaydi.
 */
export function localized<T extends object>(labels: T): T {
  const cached = proxies.get(labels)
  if (cached) return cached as T
  const proxy = new Proxy(labels, {
    get: (target, key, receiver) => {
      const value: unknown = Reflect.get(target, key, receiver)
      if (typeof key === 'string' && LOCALIZED_SKIP.has(key)) return value
      if (typeof value === 'string') return t(value)
      if (value && typeof value === 'object') return localized(value)
      return value
    },
  })
  proxies.set(labels, proxy)
  return proxy
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useLang(): Lang {
  return useSyncExternalStore(subscribe, getLang)
}
