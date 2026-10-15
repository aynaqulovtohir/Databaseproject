import { BarChart3, BookOpen, ClipboardCheck, ClipboardList, FlaskConical, Home, UserRound, Users, UsersRound, type LucideIcon } from 'lucide-react'

import type { Role } from '@/lib/types'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** true bo'lsa, faqat manzil to'liq mos kelganda faol ko'rinadi */
  end?: boolean
}

const HOME: NavItem = { to: '/', label: 'Bosh sahifa', icon: Home, end: true }
const LEARNING_ITEMS: NavItem[] = [
  { to: '/materials', label: 'Materiallar', icon: BookOpen },
  { to: '/assignments', label: 'Topshiriqlar', icon: ClipboardList },
  { to: '/labs', label: 'Virtual laboratoriya', icon: FlaskConical },
  { to: '/quizzes', label: 'Testlar', icon: ClipboardCheck },
]
const COMMON_ITEMS: NavItem[] = [{ to: '/profile', label: 'Profil', icon: UserRound }]

const ROLE_ITEMS: Record<Role, NavItem[]> = {
  admin: [
    HOME,
    { to: '/users', label: 'Foydalanuvchilar', icon: Users },
    { to: '/groups', label: 'Guruhlar', icon: UsersRound },
    ...LEARNING_ITEMS,
    { to: '/statistics', label: 'Statistika', icon: BarChart3 },
  ],
  teacher: [HOME, ...LEARNING_ITEMS, { to: '/statistics', label: 'Statistika', icon: BarChart3 }],
  student: [HOME, ...LEARNING_ITEMS],
}

export function navItemsFor(role: Role): NavItem[] {
  return [...ROLE_ITEMS[role], ...COMMON_ITEMS]
}
