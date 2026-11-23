import { useQuery } from '@tanstack/react-query'
import { ClipboardCheck, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/PageHeader'
import { QuizDialog } from '@/components/QuizDialog'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useUser } from '@/lib/auth'
import { groupNames, useGroupOptions } from '@/lib/groups'
import { quizTiming } from '@/lib/quiz'
import { QUIZ_KIND_LABELS, type Quiz } from '@/lib/types'
import { t } from '@/lib/i18n'

function QuizStatusBadge({ quiz }: { quiz: Quiz }) {
  const attempt = quiz.my_attempt
  if (attempt?.status === 'submitted') {
    if (quiz.kind === 'survey') return <Badge className="bg-emerald-100 text-emerald-800">{t('Javob berilgan')}</Badge>
    return <Badge className="bg-emerald-100 text-emerald-800 tabular-nums">{t('Natija: {percent}%', { percent: attempt.percent })}</Badge>
  }
  if (attempt?.status === 'in_progress') return <Badge className="bg-amber-100 text-amber-800">{t('Boshlangan')}</Badge>
  if (quiz.is_open === false) return <Badge variant="outline">{t('Yopiq')}</Badge>
  return <Badge variant="outline">{t('Topshirilmagan')}</Badge>
}

export function QuizzesPage() {
  const user = useUser()
  const isStaff = user.role !== 'student'
  const { groups } = useGroupOptions()
  const [creating, setCreating] = useState(false)
  const quizzes = useQuery({ queryKey: ['quizzes'], queryFn: () => api<Quiz[]>('/quizzes/') })

  const addButton = isStaff ? (
    <Button size="lg" onClick={() => setCreating(true)}>
      <Plus aria-hidden="true" />
      {t("Test qo'shish")}
    </Button>
  ) : null

  let content
  if (quizzes.isPending) {
    content = <ListSkeleton />
  } else if (quizzes.isError) {
    content = <ErrorState error={quizzes.error} onRetry={() => void quizzes.refetch()} />
  } else if (!quizzes.data.length) {
    content = (
      <EmptyState
        icon={ClipboardCheck}
        title={t("Hali test yo'q")}
        description={
          isStaff
            ? t("Tajriba uchun avval kirish testini yarating: u o'qitishdan oldingi bilimni o'lchaydi.")
            : t("O'qituvchi test berganda shu yerda ko'rinadi.")
        }
        action={addButton}
      />
    )
  } else {
    content = (
      <ul className="grid gap-3">
        {quizzes.data.map((quiz) => (
          <li key={quiz.id}>
            <Link
              to={`/quizzes/${quiz.id}`}
              className="block rounded-md bg-card p-5 shadow-(--card-shadow) transition-shadow outline-none hover:shadow-[0_0_30px_rgb(1_41_112/20%)] focus-visible:ring-3 focus-visible:ring-ring/50 dark:ring-1 dark:ring-foreground/10"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="min-w-0 font-medium">
                  {quiz.title}
                  <Badge variant="outline" className="ml-2 align-middle">
                    {QUIZ_KIND_LABELS[quiz.kind]}
                  </Badge>
                </h2>
                {isStaff ? (
                  <span className="text-xs text-muted-foreground">{t('{attempt_count} ta talaba boshlagan', { attempt_count: quiz.attempt_count })}</span>
                ) : (
                  <QuizStatusBadge quiz={quiz} />
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {quizTiming(quiz)}
                {isStaff ? ` · ${t('Guruhlar: {groups}', { groups: groupNames(quiz.groups, groups) })}` : ''}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <>
      <PageHeader
        title={t('Testlar')}
        description={
          isStaff
            ? t("Kirish va chiqish testlari: o'qitish samaradorligini o'lchash uchun.")
            : t('Har bir test bir marta topshiriladi. Boshlaganingizdan keyin vaqt hisoblanadi.')
        }
        actions={isStaff && quizzes.data?.length ? addButton : null}
      />
      {content}
      {creating ? <QuizDialog onClose={() => setCreating(false)} /> : null}
    </>
  )
}
