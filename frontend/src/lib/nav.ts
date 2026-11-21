import {
  BarChart3,
  BookOpen,
  BotMessageSquare,
  ClipboardCheck,
  ClipboardList,
  Coins,
  EyeOff,
  FlaskConical,
  Gauge,
  Home,
  ShieldAlert,
  UserRound,
  Users,
  UsersRound,
  type LucideIcon,
} from 'lucide-react'

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
const STAFF_ITEMS: NavItem[] = [
  { to: '/statistics', label: 'Statistika', icon: BarChart3 },
  { to: '/competence', label: 'Kompetentlik', icon: Gauge },
  { to: '/risk', label: 'Erta ogohlantirish', icon: ShieldAlert },
  { to: '/ai-quality', label: 'AI sifati', icon: BotMessageSquare },
  { to: '/blind-review', label: "Ko'r baholash", icon: EyeOff },
]
const COMMON_ITEMS: NavItem[] = [{ to: '/profile', label: 'Profil', icon: UserRound }]

const ROLE_ITEMS: Record<Role, NavItem[]> = {
  admin: [
    HOME,
    { to: '/users', label: 'Foydalanuvchilar', icon: Users },
    { to: '/groups', label: 'Guruhlar', icon: UsersRound },
    ...LEARNING_ITEMS,
    ...STAFF_ITEMS,
    { to: '/ai-usage', label: 'AI xarajati', icon: Coins },
  ],
  teacher: [HOME, ...LEARNING_ITEMS, ...STAFF_ITEMS],
  student: [HOME, ...LEARNING_ITEMS],
}

export function navItemsFor(role: Role): NavItem[] {
  return [...ROLE_ITEMS[role], ...COMMON_ITEMS]
}

export interface NavSection {
  /** Yon menyudagi bo'lim sarlavhasi (NiceAdmin "nav-heading"); bo'sh bo'lsa sarlavhasiz */
  heading?: string
  items: NavItem[]
}

const ADMIN_ITEMS: NavItem[] = [
  { to: '/users', label: 'Foydalanuvchilar', icon: Users },
  { to: '/groups', label: 'Guruhlar', icon: UsersRound },
  { to: '/ai-usage', label: 'AI xarajati', icon: Coins },
]

/** Yon menyu bo'limlari. navItemsFor bilan bir xil sahifalar, faqat guruhlangan. */
export function navSectionsFor(role: Role): NavSection[] {
  const sections: NavSection[] = [
    { items: [HOME] },
    { heading: "O'quv jarayoni", items: LEARNING_ITEMS },
  ]
  if (role !== 'student') sections.push({ heading: 'Tahlil va tadqiqot', items: STAFF_ITEMS })
  if (role === 'admin') sections.push({ heading: 'Boshqaruv', items: ADMIN_ITEMS })
  sections.push({ heading: 'Hisob', items: COMMON_ITEMS })
  return sections
}

/** Manzilga mos menyu bandi (ichki sahifalar uchun ham: /labs/5 → Virtual laboratoriya). */
export function navItemForPath(role: Role, pathname: string): NavItem | undefined {
  if (pathname.startsWith('/submissions/')) pathname = '/assignments'
  return navItemsFor(role).find(
    (item) => item.to !== '/' && (pathname === item.to || pathname.startsWith(`${item.to}/`)),
  )
}
