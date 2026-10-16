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
  type SurveySegment,
  type SurveySummary,
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

function ResultView({ result, survey = false }: { result: QuizResult; survey?: boolean }) {
  if (survey) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Rahmat!</CardTitle>
          <CardDescription>
            Javoblaringiz qabul qilindi ({formatDateTime(result.submitted_at)}). O'qituvchi alohida javoblaringizni
            ko'rmaydi, faqat guruh bo'yicha umumiy natijani ko'radi.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }
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

function SubmittedView({ quizId, survey }: { quizId: number; survey: boolean }) {
  const result = useQuery({
    queryKey: ['quiz-result', quizId],
    queryFn: () => api<QuizResult>(`/quizzes/${quizId}/result/`),
  })
  if (result.isPending) return <ListSkeleton rows={2} />
  if (result.isError) return <ErrorState error={result.error} onRetry={() => void result.refetch()} />
  return <ResultView result={result.data} survey={survey} />
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
  const survey = quiz.kind === 'survey'

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
          {survey ? 'Yuborish' : 'Topshirish'}
        </Button>
      </div>

      {taking.questions.map((question, index) => {
        const single = question.kind !== 'multiple'
        const likert = question.kind === 'likert'
        const selected = answers[String(question.id)] ?? []
        return (
          <Card key={question.id}>
            <CardHeader>
              <CardTitle className="text-base font-medium whitespace-pre-wrap">
                {index + 1}. {question.text}
              </CardTitle>
              <CardDescription>
                {likert
                  ? 'Bu fikrga qanchalik qo\'shilasiz?'
                  : `${single ? 'Bitta javobni tanlang' : 'Barcha to\'g\'ri javoblarni belgilang'} · ${question.points} ball`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <fieldset className={cn('grid gap-2', likert && 'sm:grid-cols-5')}>
                <legend className="sr-only">{index + 1}-savol javoblari</legend>
                {question.choices.map((choice, position) => (
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
                    <span className="whitespace-pre-wrap">
                      {likert ? `${position + 1} — ` : ''}
                      {choice.text}
                    </span>
                  </label>
                ))}
              </fieldset>
            </CardContent>
          </Card>
        )
      })}

      <ConfirmDialog
        open={confirming}
        title={survey ? "So'rovnomani yuborish" : 'Testni topshirish'}
        description={
          unanswered
            ? `${unanswered} ta savolga javob bermagansiz. Yuborgandan keyin javoblarni o'zgartirib bo'lmaydi.`
            : "Yuborgandan keyin javoblarni o'zgartirib bo'lmaydi."
        }
        confirmLabel={survey ? 'Yuborish' : 'Topshirish'}
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

  const survey = quiz.kind === 'survey'
  let content
  if (finishedResult) {
    content = <ResultView result={finishedResult} survey={survey} />
  } else if (status === 'submitted') {
    content = <SubmittedView quizId={quiz.id} survey={survey} />
  } else if (!started) {
    content = (
      <Card>
        <CardHeader>
          <CardTitle>{survey ? "So'rovnomani boshlash" : 'Testni boshlash'}</CardTitle>
          <CardDescription>
            {quiz.time_limit_minutes
              ? `Boshlaganingizdan keyin ${quiz.time_limit_minutes} daqiqa vaqtingiz bo'ladi; vaqt tugasa, test avtomatik topshiriladi.`
              : 'Vaqt cheklanmagan.'}{' '}
            {survey ? "So'rovnoma" : 'Test'} faqat bir marta topshiriladi. Javoblaringiz avtomatik saqlanadi.
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
    content = result ? <ResultView result={result} survey={survey} /> : <ErrorState error={taking.error} onRetry={() => void taking.refetch()} />
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
  const survey = quiz.kind === 'survey'
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
            {survey ? null : (
              <>
                <TableHead className="text-right">Ball</TableHead>
                <TableHead className="text-right">Foiz</TableHead>
              </>
            )}
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
              {survey ? null : (
                <>
                  <TableCell className="text-right tabular-nums">{row.score === null ? '—' : `${row.score} / ${row.max_score}`}</TableCell>
                  <TableCell className="text-right tabular-nums">{row.percent === null ? '—' : `${row.percent}%`}</TableCell>
                </>
              )}
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
        <CardDescription>
          {survey
            ? "Kim javob berganini ko'rasiz, javoblarning o'zini emas."
            : average === null
              ? 'Hali hech kim topshirmagan.'
              : `O'rtacha natija: ${average}%`}
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}

function SegmentCell({ segment }: { segment: SurveySegment }) {
  if (!segment.count) return <TableCell className="text-right text-muted-foreground">—</TableCell>
  if (segment.hidden) {
    return (
      <TableCell className="text-right text-xs text-muted-foreground" title="Javoblar kam: natija maxfiylik uchun yashirilgan">
        yashirin
      </TableCell>
    )
  }
  return (
    <TableCell className="text-right tabular-nums">
      {segment.mean?.toFixed(2)}
      <span className="block text-xs text-muted-foreground">{segment.count} ta javob</span>
    </TableCell>
  )
}

/** Javoblar taqsimoti: 1 dan 5 gacha har bir qiymat ulushi bitta chiziqda */
function DistributionBar({ segment, scale }: { segment: SurveySegment; scale: string[] }) {
  if (!segment.count) return <span className="text-xs text-muted-foreground">Javob yo'q</span>
  if (!segment.distribution) return <span className="text-xs text-muted-foreground">Javoblar kam</span>
  const { distribution } = segment
  const shades = ['bg-red-400', 'bg-orange-300', 'bg-zinc-300', 'bg-emerald-300', 'bg-emerald-500']
  const label = distribution.map((count, index) => `${index + 1} (${scale[index]}): ${count}`).join(', ')
  return (
    <div className="flex h-3 w-full min-w-24 overflow-hidden rounded-full bg-muted" role="img" aria-label={label} title={label}>
      {distribution.map((count, index) =>
        count ? <div key={index} className={shades[index]} style={{ width: `${(100 * count) / segment.count}%` }} /> : null,
      )}
    </div>
  )
}

function SurveyCard({ quiz }: { quiz: Quiz }) {
  const summary = useQuery({
    queryKey: ['quiz-survey', quiz.id],
    queryFn: () => api<SurveySummary>(`/quizzes/${quiz.id}/survey/`),
  })

  let content
  if (summary.isPending) content = <ListSkeleton rows={2} />
  else if (summary.isError) content = <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
  else if (!summary.data.respondents) content = <EmptyState icon={Users} title="Hali hech kim javob bermagan" />
  else
    content = (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Fikr</TableHead>
            <TableHead className="w-40">Taqsimot (1 → 5)</TableHead>
            <TableHead className="text-right">Hammasi</TableHead>
            <TableHead className="text-right">AI yoqilgan</TableHead>
            <TableHead className="text-right">Nazorat</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {summary.data.questions.map((question, index) => (
            <TableRow key={question.id}>
              <TableCell className="max-w-md whitespace-normal">
                {index + 1}. {question.text}
              </TableCell>
              <TableCell>
                <DistributionBar segment={question.all} scale={summary.data.scale} />
              </TableCell>
              <SegmentCell segment={question.all} />
              <SegmentCell segment={question.ai} />
              <SegmentCell segment={question.control} />
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle>So'rovnoma natijasi{summary.data?.respondents ? ` (${summary.data.respondents} ta javob)` : ''}</CardTitle>
        <CardDescription>
          O'rtacha qiymat 1 dan 5 gacha: 1 — mutlaqo qo'shilmayman, 5 — to'liq qo'shilaman. Talabalar ochiq javob berishi
          uchun {summary.data?.min_responses ?? 3} tadan kam javobli natija yashiriladi. Alohida javoblar anonim eksportda
          (Statistika → tadqiqot eksporti) taxallus bilan beriladi.
        </CardDescription>
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
  const survey = quiz.kind === 'survey'

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
        {survey ? <SurveyCard quiz={quiz} /> : null}
        <ResultsCard quiz={quiz} />
        {survey ? null : (
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
        )}
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
