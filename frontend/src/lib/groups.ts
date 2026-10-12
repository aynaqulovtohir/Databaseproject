import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { useUser } from '@/lib/auth'
import type { Group, GroupShort } from '@/lib/types'

/**
 * Material yoki topshiriq uchun tanlash mumkin bo'lgan guruhlar:
 * admin — barcha guruhlar, o'qituvchi — faqat o'ziga biriktirilganlar.
 */
export function useGroupOptions(): { groups: GroupShort[]; isPending: boolean } {
  const user = useUser()
  const isAdmin = user.role === 'admin'
  const query = useQuery({
    queryKey: ['groups'],
    queryFn: () => api<Group[]>('/groups/'),
    enabled: isAdmin,
  })
  if (isAdmin) return { groups: query.data ?? [], isPending: query.isPending }
  return { groups: user.teaching_groups, isPending: false }
}

export function groupNames(ids: number[] | undefined, groups: GroupShort[]): string {
  if (!ids?.length) return '—'
  return ids.map((id) => groups.find((group) => group.id === id)?.name ?? `#${id}`).join(', ')
}
