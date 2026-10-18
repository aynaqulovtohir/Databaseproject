import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, refreshAccessToken, setAccessToken, setSessionExpiredHandler } from '@/lib/api'
import type { Me } from '@/lib/types'

interface AuthContextValue {
  user: Me | null
  /** Sahifa ochilganda sessiya tekshirilayotgan payt */
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** Foydalanuvchi ma'lumotlarini serverdan qayta oladi (masalan, rozilik qaroridan keyin) */
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  const clearSession = useCallback(() => {
    setAccessToken(null)
    setUser(null)
    // Oldingi foydalanuvchining ma'lumotlari keshda qolmasligi kerak
    queryClient.clear()
  }, [queryClient])

  // Sahifa yangilanganda: cookie'dagi refresh token bilan sessiyani tiklaymiz
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        if (await refreshAccessToken()) {
          const me = await api<Me>('/auth/me/')
          if (!cancelled) setUser(me)
        }
      } catch {
        // Sessiya yo'q: login sahifasi ko'rsatiladi
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(clearSession)
    return () => setSessionExpiredHandler(null)
  }, [clearSession])

  const login = useCallback(
    async (username: string, password: string) => {
      const data = await api<{ access: string }>('/auth/login/', {
        method: 'POST',
        body: { username, password },
        auth: false,
      })
      queryClient.clear()
      setAccessToken(data.access)
      setUser(await api<Me>('/auth/me/'))
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    try {
      await api('/auth/logout/', { method: 'POST', auth: false })
    } finally {
      clearSession()
    }
  }, [clearSession])

  const refreshUser = useCallback(async () => {
    setUser(await api<Me>('/auth/me/'))
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshUser }),
    [user, loading, login, logout, refreshUser],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth faqat AuthProvider ichida ishlatiladi')
  return context
}

/** Faqat kirgan foydalanuvchi sahifalarida ishlatiladi. */
// eslint-disable-next-line react/only-export-components
export function useUser(): Me {
  const { user } = useAuth()
  if (!user) throw new Error('Foydalanuvchi tizimga kirmagan')
  return user
}

// eslint-disable-next-line react/only-export-components
export function fullName(person: { first_name: string; last_name: string; username?: string }): string {
  const name = `${person.first_name} ${person.last_name}`.trim()
  return name || person.username || 'Ismsiz'
}
