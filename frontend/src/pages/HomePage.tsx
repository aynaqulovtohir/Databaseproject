// Bosh sahifa NiceAdmin "Dashboard" uslubida: info-kartalar, faollik grafigi, so'nggi harakatlar va bo'limlar.
// Barcha raqamlar /api/dashboard/ dan (bazadagi haqiqiy ma'lumot, rol ruxsatlari backend'da).
import {
  ArrowRight,
  BarChart3,
  ClipboardCheck,
  ClipboardList,
  FlaskConical,
  GraduationCap,
  Inbox,
  Table2,
  Users,
  UsersRound,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { ActivityChart } from '@/components/ActivityChart'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { fullName, useUser } from '@/lib/auth'
import { timeAgo, useDashboard } from '@/lib/dashboard'
import { navItemsFor } from '@/lib/nav'
import { ROLE_LABELS, type DashboardCard, type DashboardTone, type Role } from '@/lib/types'
import { cn } from '@/lib/utils'

const DESCRIPTIONS: Record<Role, Record<string, string>> = {
  admin: {
    '/users': "O'qituvchi va talabalar hisoblarini yaratish, bloklash.",
    '/groups': "Guruhlar va ularga o'qituvchilarni biriktirish.",
    '/materials': "Barcha o'quv materiallari.",
    '/assignments': 'Barcha topshiriqlar va yechimlar.',
    '/labs': 'Barcha laboratoriyalar va talabalar natijalari.',
    '/quizzes': 'Kirish, chiqish va oddiy testlar natijalari.',
    '/statistics': "Xatolar, laboratoriyalar qiyinligi va guruhlarni taqqoslash.",
    '/profile': 'Parol va Telegram bildirishnomalari.',
  },
  teacher: {
    '/materials': "Guruhlaringiz uchun material qo'shish.",
    '/assignments': 'Topshiriq berish, yechimlarni tekshirish va baholash.',
    '/labs': "SQL laboratoriyalari yaratish va kim bajarganini ko'rish.",
    '/quizzes': 'Kirish va chiqish testlari tuzish, natijalarni solishtirish.',
    '/statistics': "Eng ko'p xatolar, AI ta'siri va tajriba guruhlarini taqqoslash.",
    '/profile': 'Parol va Telegram bildirishnomalari.',
  },
  student: {
    '/materials': "Guruhingizga berilgan o'quv materiallari.",
    '/assignments': "Yechim topshirish, AI tahlili va baholarni ko'rish.",
    '/labs': 'SQL kod yozib ishga tushirish, xato bo\'lsa maslahat olish.',
    '/quizzes': "O'qituvchi bergan testlarni topshirish.",
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

// NiceAdmin info-kartalari: har biriga o'z rangli doira belgisi
const CARD_STYLE: Record<string, { icon: LucideIcon; tone: string; link?: string }> = {
  assignments: { icon: ClipboardList, tone: 'bg-tone-blue-bg text-tone-blue', link: '/assignments' },
  labs: { icon: FlaskConical, tone: 'bg-tone-orange-bg text-tone-orange', link: '/labs' },
  quizzes: { icon: ClipboardCheck, tone: 'bg-tone-green-bg text-tone-green', link: '/quizzes' },
  grade: { icon: GraduationCap, tone: 'bg-tone-purple-bg text-tone-purple', link: '/assignments' },
  students: { icon: Users, tone: 'bg-tone-blue-bg text-tone-blue' },
  pending: { icon: Inbox, tone: 'bg-tone-purple-bg text-tone-purple', link: '/assignments' },
  users: { icon: Users, tone: 'bg-tone-blue-bg text-tone-blue', link: '/users' },
  groups: { icon: UsersRound, tone: 'bg-tone-green-bg text-tone-green', link: '/groups' },
}

function InfoCard({ card }: { card: DashboardCard }) {
  const style = CARD_STYLE[card.key] ?? { icon: BarChart3, tone: 'bg-tone-blue-bg text-tone-blue' }
  const body = (
    <Card className="h-full gap-0 pb-3 transition-shadow group-hover:shadow-[0_0_30px_rgb(1_41_112/18%)]">
      <CardHeader className="pb-1">
        <CardTitle>{card.label}</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center gap-4 pt-2">
        <div className={cn('flex size-16 shrink-0 items-center justify-center rounded-full', style.tone)}>
          <style.icon className="size-8" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="font-heading text-[1.75rem] leading-tight font-bold text-heading tabular-nums">{card.value}</div>
          {card.hint ? <div className="text-xs text-muted-foreground">{card.hint}</div> : null}
        </div>
      </CardContent>
    </Card>
  )
  return style.link ? (
    <Link to={style.link} className="group block h-full rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
      {body}
    </Link>
  ) : (
    body
  )
}

const BADGE_TONE: Record<DashboardTone, string> = {
  primary: 'text-primary',
  info: 'text-tone-blue',
  success: 'text-tone-green',
  warning: 'text-tone-orange',
  danger: 'text-destructive',
}

const KIND_LABEL = { submission: 'Yechim', lab_attempt: 'Laboratoriya', quiz_attempt: 'Test' } as const

function RecentActivity() {
  const { data } = useDashboard()
  const items = data?.recent ?? []
  if (items.length === 0) {
    return <EmptyState icon={Inbox} title="Hali harakat yo'q" description="Yechim, laboratoriya yoki test topshirilganda shu yerda ko'rinadi." />
  }
  return (
    <ol className="text-sm">
      {items.map((item, index) => (
        <li key={`${item.kind}-${item.link}-${index}`} className="flex gap-3">
          <div className="relative w-20 shrink-0 pt-px text-right text-xs text-muted-foreground before:absolute before:top-0 before:-right-[9px] before:bottom-0 before:w-1 before:bg-[#eceefe] dark:before:bg-border">
            {timeAgo(item.at)}
          </div>
          <span
            className={cn('relative z-[1] mt-1 size-3 shrink-0 rounded-full border-[3px] border-card bg-current', BADGE_TONE[item.tone])}
            aria-hidden="true"
          />
          <div className="min-w-0 pb-4">
            <Link to={item.link} className="font-semibold text-heading hover:text-primary">
              {item.title}
            </Link>
            <div className="text-xs text-muted-foreground">
              {KIND_LABEL[item.kind]} · {item.status}
              {item.actor ? ` · ${item.actor}` : ''}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}

function Sections() {
  const user = useUser()
  const items = navItemsFor(user.role).filter((item) => item.to !== '/')
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {items.map((item) => (
        <li key={item.to}>
          <Link
            to={item.to}
            className="group flex h-full items-start gap-3 rounded-md border border-border p-3 transition-colors outline-none hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-tone-blue-bg text-tone-blue">
              <item.icon className="size-4.5" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-semibold text-heading group-hover:text-primary">{item.label}</div>
              {DESCRIPTIONS[user.role][item.to] ? (
                <p className="mt-0.5 text-xs text-muted-foreground">{DESCRIPTIONS[user.role][item.to]}</p>
              ) : null}
            </div>
            <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function HomePage() {
  const user = useUser()
  const dashboard = useDashboard()
  const [showTable, setShowTable] = useState(false)

  return (
    <>
      <PageHeader title={`Xush kelibsiz, ${fullName(user)}`} description={roleSummary(user)} />

      {dashboard.isError ? (
        <div className="mb-5">
          <ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-3">
        <div className="grid content-start gap-5 xl:col-span-2">
          <section aria-label="Asosiy ko'rsatkichlar" className="grid gap-5 sm:grid-cols-2">
            {dashboard.isPending
              ? Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-36 rounded-md" />)
              : dashboard.data?.cards.map((card) => <InfoCard key={card.key} card={card} />)}
          </section>

          <Card>
            <CardHeader>
              <CardTitle>
                Faollik <span>| so'nggi 14 kun</span>
              </CardTitle>
              {dashboard.data ? (
                <CardAction>
                  <Button variant="ghost" size="sm" onClick={() => setShowTable((value) => !value)} aria-pressed={showTable}>
                    {showTable ? <BarChart3 aria-hidden="true" /> : <Table2 aria-hidden="true" />}
                    {showTable ? 'Grafik' : 'Jadval'}
                  </Button>
                </CardAction>
              ) : null}
            </CardHeader>
            <CardContent>
              {dashboard.data ? (
                <ActivityChart chart={dashboard.data.chart} showTable={showTable} />
              ) : (
                <Skeleton className="h-[280px] w-full" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>
                Bo'limlar <span>| tez o'tish</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Sections />
            </CardContent>
          </Card>
        </div>

        <Card className="content-start self-start">
          <CardHeader>
            <CardTitle>
              So'nggi harakatlar <span>| {user.role === 'student' ? 'sizniki' : 'talabalar'}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard.isPending ? (
              <div className="grid gap-3">
                {Array.from({ length: 5 }, (_, index) => (
                  <Skeleton key={index} className="h-10 w-full" />
                ))}
              </div>
            ) : (
              <RecentActivity />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
