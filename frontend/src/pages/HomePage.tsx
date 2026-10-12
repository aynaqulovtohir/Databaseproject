import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/PageHeader'
import { fullName, useUser } from '@/lib/auth'
import { navItemsFor } from '@/lib/nav'
import { ROLE_LABELS, type Role } from '@/lib/types'

const DESCRIPTIONS: Record<Role, Record<string, string>> = {
  admin: {
    '/users': "O'qituvchi va talabalar hisoblarini yaratish, bloklash.",
    '/groups': "Guruhlar va ularga o'qituvchilarni biriktirish.",
    '/materials': "Barcha o'quv materiallari.",
    '/assignments': 'Barcha topshiriqlar va yechimlar.',
    '/profile': 'Parol va Telegram bildirishnomalari.',
  },
  teacher: {
    '/materials': "Guruhlaringiz uchun material qo'shish.",
    '/assignments': 'Topshiriq berish, yechimlarni tekshirish va baholash.',
    '/profile': 'Parol va Telegram bildirishnomalari.',
  },
  student: {
    '/materials': "Guruhingizga berilgan o'quv materiallari.",
    '/assignments': "Yechim topshirish, AI tahlili va baholarni ko'rish.",
    '/profile': 'Parol va Telegram bildirishnomalari.',
  },
}

function roleSummary(user: ReturnType<typeof useUser>): string {
  if (user.role === 'student') {
    return user.group
      ? `Guruhingiz: ${user.group.name}`
      : 'Siz hali guruhga biriktirilmagansiz. Administratorga murojaat qiling.'
  }
  if (user.role === 'teacher') {
    const names = user.teaching_groups.map((group) => group.name).join(', ')
    return names ? `Guruhlaringiz: ${names}` : 'Sizga hali guruh biriktirilmagan. Administratorga murojaat qiling.'
  }
  return `Rolingiz: ${ROLE_LABELS[user.role]}`
}

export function HomePage() {
  const user = useUser()
  const items = navItemsFor(user.role).filter((item) => item.to !== '/')

  return (
    <>
      <PageHeader title={`Xush kelibsiz, ${fullName(user)}`} description={roleSummary(user)} />
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              className="group flex h-full items-start gap-3 rounded-xl border bg-card p-4 transition-colors outline-none hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <item.icon className="size-5" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-medium">{item.label}</div>
                <p className="mt-0.5 text-sm text-muted-foreground">{DESCRIPTIONS[user.role][item.to]}</p>
              </div>
              <ArrowRight
                className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </Link>
          </li>
        ))}
      </ul>
    </>
  )
}
