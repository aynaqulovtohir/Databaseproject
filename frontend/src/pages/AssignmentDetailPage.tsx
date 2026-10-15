import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ChevronDown, Inbox, Loader2, Pencil, Trash2 } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { AnalysisPanel } from '@/components/AnalysisPanel'
import { AssignmentDialog } from '@/components/AssignmentDialog'
import { ChatPanel } from '@/components/ChatPanel'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { PageHeader } from '@/components/PageHeader'
import { SqlCode } from '@/components/SqlCode'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { DeadlineBadge, SubmissionStatusBadge } from '@/components/SubmissionBadges'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError, errorMessage, fieldErrors } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { formatDateTime, isPast } from '@/lib/format'
import { groupNames, useGroupOptions } from '@/lib/groups'
import { MAX_SCORE, type Assignment, type MissingStudent, type Submission } from '@/lib/types'
import { cn } from '@/lib/utils'
import { NotFoundPage } from '@/pages/NotFoundPage'

const MAX_SQL_LENGTH = 50_000

function BackLink() {
  return (
    <Link
      to="/assignments"
      className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden="true" />
      Topshiriqlar
    </Link>
  )
}

function ConditionCard({ assignment, children }: { assignment: Assignment; children?: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Topshiriq sharti</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-2">
          <span>Muddat: {formatDateTime(assignment.deadline)}</span>
          <DeadlineBadge deadline={assignment.deadline} />
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <p className="text-sm whitespace-pre-wrap">{assignment.description}</p>
        {children}
      </CardContent>
    </Card>
  )
}

// ---------- Admin va o'qituvchi ----------

function StaffView({ assignment }: { assignment: Assignment }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const submissions = useQuery({
    queryKey: ['submissions', assignment.id],
    queryFn: () => api<Submission[]>(`/assignments/${assignment.id}/submissions/`),
  })

  const missing = useQuery({
    queryKey: ['missing-students', assignment.id],
    queryFn: () => api<MissingStudent[]>(`/assignments/${assignment.id}/missing-students/`),
  })

  const remove = useMutation({
    mutationFn: () => api(`/assignments/${assignment.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success("Topshiriq o'chirildi")
      void queryClient.invalidateQueries({ queryKey: ['assignments'] })
      void navigate('/assignments', { replace: true })
    },
    onError: (error) => {
      toast.error(errorMessage(error))
      setConfirmingDelete(false)
    },
  })

  let submissionsContent
  if (submissions.isPending) {
    submissionsContent = <ListSkeleton rows={2} />
  } else if (submissions.isError) {
    submissionsContent = <ErrorState error={submissions.error} onRetry={() => void submissions.refetch()} />
  } else if (!submissions.data.length) {
    submissionsContent = <EmptyState icon={Inbox} title="Hali yechim kelmagan" />
  } else {
    const rows = [...submissions.data].sort((a, b) => fullName(a.student).localeCompare(fullName(b.student)))
    submissionsContent = (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Talaba</TableHead>
            <TableHead>Holat</TableHead>
            <TableHead className="text-right">Urinish</TableHead>
            <TableHead className="text-right">Ball</TableHead>
            <TableHead>Topshirilgan</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((submission) => (
            <TableRow key={submission.id}>
              <TableCell className="font-medium">{fullName(submission.student)}</TableCell>
              <TableCell>
                <SubmissionStatusBadge submission={submission} />
              </TableCell>
              <TableCell className="text-right tabular-nums">{submission.attempt_number}</TableCell>
              <TableCell className="text-right tabular-nums">{submission.grade?.score ?? '—'}</TableCell>
              <TableCell>{formatDateTime(submission.submitted_at)}</TableCell>
              <TableCell className="text-right">
                <Button asChild variant="outline" size="lg">
                  <Link to={`/submissions/${submission.id}`}>
                    {submission.status === 'submitted' ? 'Tekshirish' : "Ko'rish"}
                  </Link>
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  let missingContent
  if (missing.isPending) {
    missingContent = <ListSkeleton rows={1} />
  } else if (missing.isError) {
    missingContent = <ErrorState error={missing.error} onRetry={() => void missing.refetch()} />
  } else if (!missing.data.length) {
    missingContent = <p className="text-sm text-muted-foreground">Barcha talabalar yechim topshirgan.</p>
  } else {
    missingContent = (
      <ul className="grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
        {missing.data.map((student) => (
          <li key={student.id} className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate">{fullName(student)}</span>
            <span className="shrink-0 text-xs text-muted-foreground">{student.group}</span>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <>
      <BackLink />
      <PageHeader
        title={assignment.title}
        description={`${fullName(assignment.author)} · Guruhlar: ${groupNames(assignment.groups, groups)}`}
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
        <ConditionCard assignment={assignment}>
          <div className="rounded-lg border bg-muted/40 p-3 text-sm">
            <div className="font-medium">Baholash mezonlari</div>
            <p className="mt-1 whitespace-pre-wrap text-muted-foreground">
              {assignment.grading_criteria?.trim() || 'Kiritilmagan.'}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">Talabaga ko'rinmaydi.</p>
          </div>
        </ConditionCard>
        <Card>
          <CardHeader>
            <CardTitle>Yechimlar</CardTitle>
            <CardDescription>Har bir talabaning oxirgi urinishi ko'rsatiladi.</CardDescription>
          </CardHeader>
          <CardContent>{submissionsContent}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Topshirmaganlar{missing.data?.length ? ` (${missing.data.length})` : ''}</CardTitle>
            <CardDescription>Topshiriq berilgan guruhlardagi hali birorta yechim yubormagan talabalar.</CardDescription>
          </CardHeader>
          <CardContent>{missingContent}</CardContent>
        </Card>
      </div>

      {editing ? <AssignmentDialog assignment={assignment} onClose={() => setEditing(false)} /> : null}
      <ConfirmDialog
        open={confirmingDelete}
        title="Topshiriqni o'chirish"
        description={`«${assignment.title}» o'chiriladi. Yechim kelgan topshiriqni o'chirib bo'lmaydi.`}
        confirmLabel="O'chirish"
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirmingDelete(false)}
      />
    </>
  )
}

// ---------- Talaba ----------

function ResultBanner({ submission }: { submission: Submission }) {
  if (submission.status === 'graded' && submission.grade) {
    return (
      <Alert>
        <AlertTitle>
          Baho: {submission.grade.score} / {MAX_SCORE}
        </AlertTitle>
        <AlertDescription className="whitespace-pre-wrap">
          {submission.grade.comment || "O'qituvchi izoh qoldirmagan."}
        </AlertDescription>
      </Alert>
    )
  }
  if (submission.status === 'returned') {
    return (
      <Alert>
        <AlertTitle>Yechim qayta ishlashga qaytarildi</AlertTitle>
        <AlertDescription className="whitespace-pre-wrap">{submission.return_comment}</AlertDescription>
      </Alert>
    )
  }
  return (
    <Alert>
      <AlertTitle>Yechim topshirildi</AlertTitle>
      <AlertDescription>
        O'qituvchi tekshirib, baho qo'yadi. Baholangunga qadar yangi urinish topshirishingiz mumkin.
      </AlertDescription>
    </Alert>
  )
}

function AttemptItem({ submission, defaultOpen }: { submission: Submission; defaultOpen: boolean }) {
  const user = useUser()
  const [open, setOpen] = useState(defaultOpen)
  return (
    <li className="rounded-lg border">
      <button
        type="button"
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-3 py-2.5 text-left text-sm outline-none hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="font-medium">{submission.attempt_number}-urinish</span>
        <SubmissionStatusBadge submission={submission} />
        <span className="ml-auto text-xs text-muted-foreground">{formatDateTime(submission.submitted_at)}</span>
        <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden="true" />
      </button>
      {/* Tahlil faqat urinish ochilganda so'raladi */}
      {open ? (
        <div className="grid gap-4 border-t p-3">
          <SqlCode code={submission.sql_code} />
          {/* Tajribaning nazorat guruhida AI ko'rsatilmaydi */}
          {user.ai_enabled ? (
            <div>
              <h3 className="mb-2 text-sm font-medium">AI tahlili</h3>
              <AnalysisPanel submissionId={submission.id} />
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  )
}

function SubmitForm({ assignment, isRetry }: { assignment: Assignment; isRetry: boolean }) {
  const queryClient = useQueryClient()
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const late = isPast(assignment.deadline)

  const mutation = useMutation({
    mutationFn: () =>
      api<Submission>(`/assignments/${assignment.id}/submissions/`, { method: 'POST', body: { sql_code: code } }),
    onSuccess: (submission) => {
      toast.success('Yechim topshirildi')
      setCode('')
      queryClient.setQueryData<Submission[]>(['submissions', assignment.id], (current) => [
        submission,
        ...(current ?? []),
      ])
      void queryClient.invalidateQueries({ queryKey: ['assignments'] })
    },
    onError: (caught) => {
      const message = fieldErrors(caught).sql_code
      if (message) setError(message)
      else toast.error(errorMessage(caught))
      // Holat o'zgargan bo'lishi mumkin (masalan, o'qituvchi baholab qo'ygan)
      void queryClient.invalidateQueries({ queryKey: ['submissions', assignment.id] })
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    mutation.mutate()
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3" noValidate>
      {late ? (
        <Alert variant="destructive">
          <AlertDescription>Muddat o'tgan: yechim «kechikkan» deb belgilanadi.</AlertDescription>
        </Alert>
      ) : null}
      <div className="grid gap-1.5">
        <label htmlFor="sql_code" className="text-sm font-medium">
          SQL kod
        </label>
        <Textarea
          id="sql_code"
          className="max-h-[32rem] min-h-48 font-mono text-sm md:text-xs"
          placeholder={'CREATE TABLE ...'}
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
          maxLength={MAX_SQL_LENGTH}
          aria-invalid={Boolean(error)}
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        {error ? (
          <p className="text-xs text-destructive" role="alert">
            {error}
          </p>
        ) : null}
      </div>
      <Button type="submit" size="lg" className="justify-self-start" disabled={mutation.isPending || !code.trim()}>
        {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
        {isRetry ? 'Yangi urinishni topshirish' : 'Yechimni topshirish'}
      </Button>
    </form>
  )
}

function StudentView({ assignment }: { assignment: Assignment }) {
  const user = useUser()
  const submissions = useQuery({
    queryKey: ['submissions', assignment.id],
    queryFn: () => api<Submission[]>(`/assignments/${assignment.id}/submissions/`),
  })

  let work
  if (submissions.isPending) {
    work = <ListSkeleton rows={2} />
  } else if (submissions.isError) {
    work = <ErrorState error={submissions.error} onRetry={() => void submissions.refetch()} />
  } else {
    // Urinishlar yangisidan eskisiga qarab keladi
    const latest = submissions.data.at(0)
    const canSubmit = !latest || latest.status !== 'graded'
    work = (
      <div className="grid gap-4">
        {latest ? <ResultBanner submission={latest} /> : null}
        {canSubmit ? <SubmitForm assignment={assignment} isRetry={Boolean(latest)} /> : null}
        {submissions.data.length ? (
          <div>
            <h3 className="mb-2 text-sm font-medium">Urinishlarim</h3>
            <ul className="grid gap-2">
              {submissions.data.map((submission, index) => (
                <AttemptItem key={submission.id} submission={submission} defaultOpen={index === 0} />
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <>
      <BackLink />
      <PageHeader title={assignment.title} description={`O'qituvchi: ${fullName(assignment.author)}`} />
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="grid gap-4">
          <ConditionCard assignment={assignment} />
          <Card>
            <CardHeader>
              <CardTitle>Mening yechimim</CardTitle>
              <CardDescription>
                Har bir topshirish alohida urinish sifatida saqlanadi va AI tomonidan tahlil qilinadi.
              </CardDescription>
            </CardHeader>
            <CardContent>{work}</CardContent>
          </Card>
        </div>
        {user.ai_enabled ? (
          <Card>
            <CardHeader>
              <CardTitle>AI yordamchi</CardTitle>
              <CardDescription>Yozishmani faqat siz ko'rasiz.</CardDescription>
            </CardHeader>
            <CardContent>
              <ChatPanel assignmentId={assignment.id} />
            </CardContent>
          </Card>
        ) : null}
      </div>
    </>
  )
}

export function AssignmentDetailPage() {
  const user = useUser()
  const params = useParams()
  const id = Number(params.id)
  const validId = Number.isInteger(id) && id > 0

  const assignment = useQuery({
    queryKey: ['assignment', id],
    queryFn: () => api<Assignment>(`/assignments/${id}/`),
    enabled: validId,
  })

  if (!validId) return <NotFoundPage />
  if (assignment.isPending) return <ListSkeleton />
  if (assignment.isError) {
    if (assignment.error instanceof ApiError && assignment.error.status === 404) return <NotFoundPage />
    return <ErrorState error={assignment.error} onRetry={() => void assignment.refetch()} />
  }

  return user.role === 'student' ? (
    <StudentView key={id} assignment={assignment.data} />
  ) : (
    <StaffView key={id} assignment={assignment.data} />
  )
}
