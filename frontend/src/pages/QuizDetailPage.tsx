import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CircleCheck, CircleX, Clock, Loader2, Pencil, Play, Send, Trash2, Users } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { PageHeader } from '@/components/PageHeader'
import { QuizDialog } from '@/components/QuizDialog'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, ApiError, errorMessage } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { formatDateTime } from '@/lib/format'
import { groupNames, useGroupOptions } from '@/lib/groups'
import { quizTiming } from '@/lib/quiz'
import { cn } from '@/lib/utils'
import {
  QUIZ_KIND_LABELS,
  type Quiz,
  type QuizAttemptStatus,
  type QuizResult,
  type QuizStudentResult,
  type QuizTaking,
} from '@/lib/types'
import { NotFoundPage } from '@/pages/NotFoundPage'

const SAVE_DELAY_MS = 800
const STATUS_LABELS: Record<QuizAttemptStatus, string> = {
  not_started: 'Boshlamagan',
  in_progress: 'Boshlagan',
  submitted: 'Topshirgan',
}

function BackLink() {
  return (
    <Link to="/quizzes" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="size-4" aria-hidden="true" />
      Testlar
    </Link>
  )
}

/** 409 javobida (test allaqachon yakunlangan) kelgan natija */
function resultFromConflict(error: unknown): QuizResult | null {
  if (error instanceof ApiError && error.status === 409 && error.data && typeof error.data === 'object') {
    return (error.data as { result?: QuizResult }).result ?? null
  }
  return null
}

function formatRemaining(milliseconds: number) {
  const total = Math.max(0, Math.ceil(milliseconds / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

// ---------- Natija ----------

function ResultView({ result }: { result: QuizResult }) {
  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Natijangiz</CardTitle>
          <CardDescription>Topshirilgan: {formatDateTime(result.submitted_at)}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="text-3xl font-semibold tabular-nums">{result.percent}%</span>
          <span className="text-sm text-muted-foreground tabular-nums">
            {result.score} / {result.max_score} ball
          </span>
        </CardContent>
      </Card>
      {result.questions ? (
        <Card>
          <CardHeader>
            <CardTitle>Javoblar</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {result.questions.map((question, index) => (
              <div key={question.id} className="grid gap-2 border-b pb-4 last:border-b-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-medium whitespace-pre-wrap">
                    {index + 1}. {question.text}
                  </p>
                  <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                    {question.earned} / {question.points}
                  </span>
                </div>
                <ul className="grid gap-1">
                  {question.choices.map((choice) => (
                    <li
                      key={choice.id}
                      className={cn(
                        'flex items-center gap-2 rounded-md px-2 py-1 text-sm',
                        choice.is_correct && 'bg-emerald-50 text-emerald-900',
                        choice.selected && !choice.is_correct && 'bg-red-50 text-red-900',
                      )}
                    >
                      {choice.is_correct ? (
                        <CircleCheck className="size-4 shrink-0" aria-label="to'g'ri javob" />
                      ) : choice.selected ? (
                        <CircleX className="size-4 shrink-0" aria-label="noto'g'ri tanlangan" />
                      ) : (
                        <span className="size-4 shrink-0" aria-hidden="true" />
                      )}
                      <span>{choice.text}</span>
                      {choice.selected ? <span className="ml-auto text-xs">sizning javobingiz</span> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">To'g'ri javoblar ko'rsatilmaydi: o'qituvchi bu test uchun ularni yopgan.</p>
      )}
    </div>
  )
}

function SubmittedView({ quizId }: { quizId: number }) {
  const result = useQuery({
    queryKey: ['quiz-result', quizId],
    queryFn: () => api<QuizResult>(`/quizzes/${quizId}/result/`),
  })
  if (result.isPending) return <ListSkeleton rows={2} />
  if (result.isError) return <ErrorState error={result.error} onRetry={() => void result.refetch()} />
  return <ResultView result={result.data} />
}

// ---------- Testni yechish ----------

function Taker({ quiz, taking, onFinished }: { quiz: Quiz; taking: QuizTaking; onFinished: (result: QuizResult) => void }) {
  const [answers, setAnswers] = useState<Record<string, number[]>>(taking.answers)
  const [saveState, setSaveState] = useState<'saved' | 'saving' | 'error'>('saved')
  const [confirming, setConfirming] = useState(false)
  // Server va brauzer soatlari farqi: qolgan vaqt server vaqti bo'yicha hisoblanadi
  const [clockOffset] = useState(() => Date.parse(taking.server_now) - Date.now())
  const [now, setNow] = useState(() => Date.now())
  const firstRender = useRef(true)

  const submit = useMutation({
    mutationFn: () => api<QuizResult>(`/quizzes/${quiz.id}/submit/`, { method: 'POST', body: { answers } }),
    onSuccess: onFinished,
    onError: (error) => {
      const result = resultFromConflict(error)
      if (result) onFinished(result)
      else toast.error(errorMessage(error))
    },
  })

  const finish = useCallback(() => {
    if (!submit.isPending && !submit.isSuccess) submit.mutate()
  }, [submit])

  // Javoblar o'zgarganda biroz kutib saqlanadi
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    setSaveState('saving')
    const timer = window.setTimeout(() => {
      api(`/quizzes/${quiz.id}/answers/`, { method: 'PUT', body: { answers } })
        .then(() => setSaveState('saved'))
        .catch((error: unknown) => {
          const result = resultFromConflict(error)
          if (result) onFinished(result)
          else setSaveState('error')
        })
    }, SAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [answers, quiz.id, onFinished])

  const deadline = taking.deadline ? Date.parse(taking.deadline) : null
  const remaining = deadline === null ? null : deadline - (now + clockOffset)

  useEffect(() => {
    if (deadline === null) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [deadline])

  // Vaqt tugadi: test avtomatik topshiriladi
  useEffect(() => {
    if (remaining !== null && remaining <= 0) finish()
  }, [remaining, finish])

  function toggle(questionId: number, choiceId: number, single: boolean) {
    const key = String(questionId)
    const current = answers[key] ?? []
    const next = single ? [choiceId] : current.includes(choiceId) ? current.filter((id) => id !== choiceId) : [...current, choiceId]
    setAnswers({ ...answers, [key]: next })
  }

  const answered = taking.questions.filter((question) => (answers[String(question.id)] ?? []).length).length
  const unanswered = taking.questions.length - answered

  return (
    <div className="grid gap-4">
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-background/95 p-3 backdrop-blur">
        {remaining !== null ? (
          <span
            className={cn('flex items-center gap-1.5 font-semibold tabular-nums', remaining < 60_000 && 'text-destructive')}
            role="timer"
            aria-live={remaining < 60_000 ? 'assertive' : 'off'}
          >
            <Clock className="size-4" aria-hidden="true" />
            {formatRemaining(remaining)}
          </span>
        ) : null}
        <span className="text-sm text-muted-foreground">
          {answered} / {taking.questions.length} savolga javob berildi
        </span>
        <span className="text-xs text-muted-foreground" aria-live="polite">
          {saveState === 'saving' ? 'Saqlanmoqda…' : saveState === 'error' ? "Saqlanmadi: internetni tekshiring" : 'Saqlandi'}
        </span>
        <Button className="ml-auto" disabled={submit.isPending} onClick={() => setConfirming(true)}>
          {submit.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
          Topshirish
        </Button>
      </div>

      {taking.questions.map((question, index) => {
        const single = question.kind === 'single'
        const selected = answers[String(question.id)] ?? []
        return (
          <Card key={question.id}>
            <CardHeader>
              <CardTitle className="text-base font-medium whitespace-pre-wrap">
                {index + 1}. {question.text}
              </CardTitle>
              <CardDescription>
                {single ? 'Bitta javobni tanlang' : 'Barcha to\'g\'ri javoblarni belgilang'} · {question.points} ball
              </CardDescription>
            </CardHeader>
            <CardContent>
              <fieldset className="grid gap-2">
                <legend className="sr-only">{index + 1}-savol javoblari</legend>
                {question.choices.map((choice) => (
                  <label
                    key={choice.id}
                    className={cn(
                      'flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 text-sm transition-colors hover:bg-muted/50',
                      selected.includes(choice.id) && 'border-primary bg-primary/5',
                    )}
                  >
                    <input
                      type={single ? 'radio' : 'checkbox'}
                      name={`question-${question.id}`}
                      className="mt-0.5 size-4 shrink-0"
                      checked={selected.includes(choice.id)}
                      onChange={() => toggle(question.id, choice.id, single)}
                    />
                    <span className="whitespace-pre-wrap">{choice.text}</span>
                  </label>
                ))}
              </fieldset>
            </CardContent>
          </Card>
        )
      })}

      <ConfirmDialog
        open={confirming}
        title="Testni topshirish"
        description={
          unanswered
            ? `${unanswered} ta savolga javob bermagansiz. Topshirgandan keyin javoblarni o'zgartirib bo'lmaydi.`
            : "Topshirgandan keyin javoblarni o'zgartirib bo'lmaydi."
        }
        confirmLabel="Topshirish"
        pending={submit.isPending}
        onConfirm={() => {
          setConfirming(false)
          finish()
        }}
        onClose={() => setConfirming(false)}
      />
    </div>
  )
}

function StudentView({ quiz }: { quiz: Quiz }) {
  const queryClient = useQueryClient()
  const status = quiz.my_attempt?.status ?? 'not_started'
  const [started, setStarted] = useState(status === 'in_progress')
  const [finishedResult, setFinishedResult] = useState<QuizResult | null>(null)

  const taking = useQuery({
    queryKey: ['quiz-taking', quiz.id],
    queryFn: () => api<QuizTaking>(`/quizzes/${quiz.id}/start/`, { method: 'POST' }),
    enabled: started && status !== 'submitted',
    staleTime: Infinity,
    retry: false,
  })

  const handleFinished = useCallback(
    (result: QuizResult) => {
      setFinishedResult(result)
      queryClient.setQueryData(['quiz-result', quiz.id], result)
      void queryClient.invalidateQueries({ queryKey: ['quiz', quiz.id] })
      void queryClient.invalidateQueries({ queryKey: ['quizzes'] })
      window.scrollTo({ top: 0 })
    },
    [queryClient, quiz.id],
  )

  let content
  if (finishedResult) {
    content = <ResultView result={finishedResult} />
  } else if (status === 'submitted') {
    content = <SubmittedView quizId={quiz.id} />
  } else if (!started) {
    content = (
      <Card>
        <CardHeader>
          <CardTitle>Testni boshlash</CardTitle>
          <CardDescription>
            {quiz.time_limit_minutes
              ? `Boshlaganingizdan keyin ${quiz.time_limit_minutes} daqiqa vaqtingiz bo'ladi; vaqt tugasa, test avtomatik topshiriladi.`
              : 'Vaqt cheklanmagan.'}{' '}
            Test faqat bir marta topshiriladi. Javoblaringiz avtomatik saqlanadi.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {quiz.is_open ? (
            <Button size="lg" onClick={() => setStarted(true)}>
              <Play aria-hidden="true" />
              Boshlash
            </Button>
          ) : (
            <p className="text-sm text-muted-foreground">
              Test hozir yopiq.{quiz.opens_at ? ` Ochilish vaqti: ${formatDateTime(quiz.opens_at)}.` : ''}
            </p>
          )}
        </CardContent>
      </Card>
    )
  } else if (taking.isPending) {
    content = <ListSkeleton />
  } else if (taking.isError) {
    const result = resultFromConflict(taking.error)
    content = result ? <ResultView result={result} /> : <ErrorState error={taking.error} onRetry={() => void taking.refetch()} />
  } else {
    content = <Taker quiz={quiz} taking={taking.data} onFinished={handleFinished} />
  }

  return (
    <>
      <BackLink />
      <PageHeader title={quiz.title} description={`${QUIZ_KIND_LABELS[quiz.kind]} · ${quizTiming(quiz)}`} />
      {quiz.description && status === 'not_started' && !started ? (
        <p className="mb-4 text-sm whitespace-pre-wrap">{quiz.description}</p>
      ) : null}
      {content}
    </>
  )
}

// ---------- Admin va o'qituvchi ----------

function ResultsCard({ quiz }: { quiz: Quiz }) {
  const results = useQuery({
    queryKey: ['quiz-results', quiz.id],
    queryFn: () => api<QuizStudentResult[]>(`/quizzes/${quiz.id}/results/`),
  })

  let content
  if (results.isPending) content = <ListSkeleton rows={2} />
  else if (results.isError) content = <ErrorState error={results.error} onRetry={() => void results.refetch()} />
  else if (!results.data.length) content = <EmptyState icon={Users} title="Bu guruhlarda hali talaba yo'q" />
  else
    content = (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Talaba</TableHead>
            <TableHead>Guruh</TableHead>
            <TableHead>Holat</TableHead>
            <TableHead className="text-right">Ball</TableHead>
            <TableHead className="text-right">Foiz</TableHead>
            <TableHead>Topshirilgan</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.data.map((row) => (
            <TableRow key={row.id}>
              <TableCell className="font-medium">{fullName(row)}</TableCell>
              <TableCell>{row.group}</TableCell>
              <TableCell>
                <Badge variant={row.status === 'submitted' ? 'default' : 'outline'}>{STATUS_LABELS[row.status]}</Badge>
              </TableCell>
              <TableCell className="text-right tabular-nums">{row.score === null ? '—' : `${row.score} / ${row.max_score}`}</TableCell>
              <TableCell className="text-right tabular-nums">{row.percent === null ? '—' : `${row.percent}%`}</TableCell>
              <TableCell>{formatDateTime(row.submitted_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )

  const submitted = results.data?.filter((row) => row.status === 'submitted') ?? []
  const average = submitted.length
    ? Math.round((submitted.reduce((sum, row) => sum + (row.percent ?? 0), 0) / submitted.length) * 10) / 10
    : null

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Natijalar
          {results.data?.length ? ` (${submitted.length} / ${results.data.length} topshirgan)` : ''}
        </CardTitle>
        <CardDescription>{average === null ? 'Hali hech kim topshirmagan.' : `O'rtacha natija: ${average}%`}</CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}

function StaffView({ quiz }: { quiz: Quiz }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const remove = useMutation({
    mutationFn: () => api(`/quizzes/${quiz.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success("Test o'chirildi")
      void queryClient.invalidateQueries({ queryKey: ['quizzes'] })
      void navigate('/quizzes', { replace: true })
    },
    onError: (error) => {
      toast.error(errorMessage(error))
      setConfirmingDelete(false)
    },
  })

  return (
    <>
      <BackLink />
      <PageHeader
        title={quiz.title}
        description={`${QUIZ_KIND_LABELS[quiz.kind]} · ${quizTiming(quiz)} · Guruhlar: ${groupNames(quiz.groups, groups)}`}
        actions={
          <>
            <Button variant="outline" size="lg" onClick={() => setEditing(true)}>
              <Pencil aria-hidden="true" />
              Tahrirlash
            </Button>
            <Button variant="destructive" size="lg" onClick={() => setConfirmingDelete(true)}>
              <Trash2 aria-hidden="true" />
              O'chirish
            </Button>
          </>
        }
      />
      <div className="grid gap-4">
        <ResultsCard quiz={quiz} />
        <Card>
          <CardHeader>
            <CardTitle>Savollar</CardTitle>
            <CardDescription>
              To'g'ri javoblar yashil bilan belgilangan.{' '}
              {quiz.show_answers ? "Talabaga topshirgandan keyin ko'rsatiladi." : "Talabaga ko'rsatilmaydi."}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {(quiz.questions ?? []).map((question, index) => (
              <div key={question.id ?? index} className="grid gap-2 border-b pb-4 last:border-b-0 last:pb-0">
                <p className="text-sm font-medium whitespace-pre-wrap">
                  {index + 1}. {question.text}{' '}
                  <span className="font-normal text-muted-foreground">
                    ({question.kind === 'single' ? 'bitta javob' : 'bir nechta javob'}, {question.points} ball)
                  </span>
                </p>
                <ul className="grid gap-1">
                  {question.choices.map((choice, position) => (
                    <li
                      key={choice.id ?? position}
                      className={cn('flex items-center gap-2 rounded-md px-2 py-1 text-sm', choice.is_correct && 'bg-emerald-50 text-emerald-900')}
                    >
                      {choice.is_correct ? (
                        <CircleCheck className="size-4 shrink-0" aria-label="to'g'ri javob" />
                      ) : (
                        <span className="size-4 shrink-0" aria-hidden="true" />
                      )}
                      {choice.text}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {editing ? <QuizDialog quiz={quiz} onClose={() => setEditing(false)} /> : null}
      <ConfirmDialog
        open={confirmingDelete}
        title="Testni o'chirish"
        description={`«${quiz.title}» o'chiriladi. Talabalar topshirgan test o'chirilmaydi.`}
        confirmLabel="O'chirish"
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirmingDelete(false)}
      />
    </>
  )
}

export function QuizDetailPage() {
  const user = useUser()
  const params = useParams()
  const id = Number(params.id)
  const validId = Number.isInteger(id) && id > 0

  const quiz = useQuery({ queryKey: ['quiz', id], queryFn: () => api<Quiz>(`/quizzes/${id}/`), enabled: validId })

  if (!validId) return <NotFoundPage />
  if (quiz.isPending) return <ListSkeleton />
  if (quiz.isError) {
    if (quiz.error instanceof ApiError && quiz.error.status === 404) return <NotFoundPage />
    return <ErrorState error={quiz.error} onRetry={() => void quiz.refetch()} />
  }
  return user.role === 'student' ? <StudentView key={id} quiz={quiz.data} /> : <StaffView key={id} quiz={quiz.data} />
}
