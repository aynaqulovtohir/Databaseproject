// Backend bilan ishlash: access token faqat xotirada turadi (localStorage'ga yozilmaydi),
// refresh token esa httpOnly cookie'da, uni JavaScript o'qiy olmaydi.

const API_BASE = '/api'

let accessToken: string | null = null
let onSessionExpired: (() => void) | null = null
// Bir vaqtda bir nechta so'rov 401 olsa, token faqat bir marta yangilanadi
let refreshInFlight: Promise<boolean> | null = null

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, data: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler
}

/** Cookie'dagi refresh token orqali yangi access token oladi. */
export function refreshAccessToken(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh/`, {
        method: 'POST',
        credentials: 'same-origin',
      })
      if (!response.ok) {
        accessToken = null
        return false
      }
      const data = (await response.json()) as { access: string }
      accessToken = data.access
      return true
    } catch {
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

interface RequestOptions {
  method?: string
  body?: unknown
  /** false bo'lsa, 401 da tokenni yangilashga urinilmaydi (login so'rovi uchun) */
  auth?: boolean
  signal?: AbortSignal
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (options.body instanceof FormData) {
    body = options.body
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (options.auth !== false && accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }
  return fetch(`${API_BASE}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body,
    credentials: 'same-origin',
    signal: options.signal,
  })
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return null
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export async function apiFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  let response: Response
  try {
    response = await send(path, options)
    if (response.status === 401 && options.auth !== false) {
      // Access token muddati tugagan bo'lishi mumkin: bir marta yangilab, qayta urinamiz
      if (await refreshAccessToken()) {
        response = await send(path, options)
      } else {
        onSessionExpired?.()
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, null, "Serverga ulanib bo'lmadi. Internet aloqasini tekshiring.")
  }
  return response
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await apiFetch(path, options)
  const data = await parseBody(response)
  if (!response.ok) {
    throw new ApiError(response.status, data, extractMessage(response.status, data))
  }
  return data as T
}

const STATUS_MESSAGES: Record<number, string> = {
  401: 'Sessiya tugagan. Qayta kiring.',
  403: "Bu amal uchun ruxsatingiz yo'q.",
  404: "Ma'lumot topilmadi.",
  413: 'Yuborilgan fayl yoki matn juda katta.',
  429: "So'rovlar juda ko'p. Birozdan keyin qayta urinib ko'ring.",
}

// Backend'ning ba'zi standart xabarlari inglizcha: ularni o'zbekchaga almashtiramiz
const KNOWN_MESSAGES: Record<string, string> = {
  'No active account found with the given credentials': "Login yoki parol noto'g'ri.",
  'Authentication credentials were not provided.': 'Sessiya tugagan. Qayta kiring.',
}

function firstString(value: unknown): string | null {
  if (typeof value === 'string') return value
  // Ichma-ich xatolar ham o'qiladi, masalan: {"questions": [{}, {"choices": ["..."]}]}
  const items = Array.isArray(value) ? value : value && typeof value === 'object' ? Object.values(value) : []
  for (const item of items) {
    const found = firstString(item)
    if (found) return found
  }
  return null
}

function extractMessage(status: number, data: unknown): string {
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const record = data as Record<string, unknown>
    const detail = firstString(record.detail)
    if (detail) {
      if (KNOWN_MESSAGES[detail]) return KNOWN_MESSAGES[detail]
      // Limit xabari inglizcha keladi ("Request was throttled...")
      if (status === 429 && detail.startsWith('Request was throttled')) return STATUS_MESSAGES[429]
      return detail
    }
    // Maydon xatolari: {"username": ["..."]}
    for (const value of Object.values(record)) {
      const message = firstString(value)
      if (message) return message
    }
  }
  if (status >= 500) return "Serverda xato yuz berdi. Keyinroq qayta urinib ko'ring."
  return STATUS_MESSAGES[status] ?? `Xato yuz berdi (${status}).`
}

/** Forma maydonlari bo'yicha xatolar: {"username": "Bu login band"} */
export function fieldErrors(error: unknown): Record<string, string> {
  const result: Record<string, string> = {}
  if (error instanceof ApiError && error.data && typeof error.data === 'object' && !Array.isArray(error.data)) {
    for (const [field, value] of Object.entries(error.data as Record<string, unknown>)) {
      const message = firstString(value)
      if (message && field !== 'detail') result[field] = message
    }
  }
  return result
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Kutilmagan xato yuz berdi.'
}
