import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Dashboard } from '@/lib/types'
import { t } from '@/lib/i18n'

/** Bosh sahifa va sarlavhadagi bildirishnomalar bitta so'rovdan foydalanadi. */
export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: ({ signal }) => api<Dashboard>('/dashboard/', { signal }),
    refetchInterval: 120_000,
  })
}

/** "5 daqiqa oldin" ko'rinishidagi qisqa vaqt (NiceAdmin faollik lentasi uslubida). */
export function timeAgo(iso: string, now = Date.now()): string {
  const diff = Math.round((now - new Date(iso).getTime()) / 1000)
  const future = diff < 0
  const abs = Math.abs(diff)
  if (abs < 60) return t('hozir')
  if (abs < 3600) {
    const n = Math.floor(abs / 60)
    return future ? t('{n} daqiqa qoldi', { n }) : t('{n} daqiqa oldin', { n })
  }
  if (abs < 86_400) {
    const n = Math.floor(abs / 3600)
    return future ? t('{n} soat qoldi', { n }) : t('{n} soat oldin', { n })
  }
  const n = Math.floor(abs / 86_400)
  return future ? t('{n} kun qoldi', { n }) : t('{n} kun oldin', { n })
}
