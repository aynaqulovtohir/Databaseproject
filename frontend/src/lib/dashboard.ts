import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type { Dashboard } from '@/lib/types'

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
  let text: string
  if (abs < 60) text = 'hozir'
  else if (abs < 3600) text = `${Math.floor(abs / 60)} daqiqa`
  else if (abs < 86_400) text = `${Math.floor(abs / 3600)} soat`
  else text = `${Math.floor(abs / 86_400)} kun`
  if (text === 'hozir') return text
  return future ? `${text} qoldi` : `${text} oldin`
}
