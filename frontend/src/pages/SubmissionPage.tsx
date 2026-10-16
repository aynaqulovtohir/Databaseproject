import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2, Undo2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { AnalysisPanel, useAnalysis } from '@/components/AnalysisPanel'
import { ErEditor } from '@/components/ErEditor'
import { FormField } from '@/components/FormField'
import { PageHeader } from '@/components/PageHeader'
import { SqlCode } from '@/components/SqlCode'
import { ErrorState, ListSkeleton } from '@/components/States'
import { SubmissionStatusBadge } from '@/components/SubmissionBadges'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '@/lib/api'
import { fullName } from '@/lib/auth'
import { applyFormError } from '@/lib/forms'
import { formatDateTime } from '@/lib/format'
import { MAX_SCORE, type Assignment, type RubricCriterion, type Submission } from '@/lib/types'
import { cn } from '@/lib/utils'
import { NotFoundPage } from '@/pages/NotFoundPage'

function useReviewMutation(submission: Submission, request: () => Promise<Submission>, successText: string) {
  const queryClient = useQueryClient()
  const [errors, setErrors] = useState<Record<string, string>>({})
  const mutation = useMutation({
    mutationFn: request,
    onSuccess: (updated) => {
      toast.success(successText)
      setErrors({})
      queryClient.setQueryData(['submission', updated.id], updated)
      void queryClient.invalidateQueries({ queryKey: ['submissions', submission.assignment] })
    },
    onError: (error) => {
      applyFormError(error, ['score', 'rubric_scores', 'comment'], setErrors)
      // Talaba shu orada yangi urinish topshirgan bo'lishi mumkin
      void queryClient.invalidateQueries({ queryKey: ['submissions', submission.assignment] })
    },
  })
  return { mutation, errors }
}

function GradeForm({
  submission,
  criteria,
  disabled,
}: {
  submission: Submission
  /** Shu yechim baholanadigan rubrika mezonlari (bo'sh bo'lsa — oddiy 0–100 ball) */
  criteria: RubricCriterion[]
  disabled: boolean
}) {
  const analysis = useAnalysis(submission.id)
  const [score, setScore] = useState(submission.grade ? String(submission.grade.score) : '')
  const [criterionScores, setCriterionScores] = useState<string[]>(
    criteria.map((_, index) => {
      const value = submission.grade?.rubric_scores?.[index]?.score
      return value === undefined ? '' : String(value)
    }),
  )
  const [comment, setComment] = useState(submission.grade?.comment ?? '')
  const suggested = analysis.data?.status === 'done' ? analysis.data.suggested_score : null
  const useRubric = criteria.length > 0
  const maxScore = useRubric ? criteria.reduce((sum, item) => sum + item.points, 0) : MAX_SCORE

  const { mutation, errors } = useReviewMutation(
    submission,
    () =>
      api<Submission>(`/submissions/${submission.id}/grade/`, {
        method: 'PUT',
        body: useRubric
          ? { rubric_scores: criterionScores.map((value) => Number(value)), comment }
          : { score: Number(score), comment },
      }),
    submission.grade ? 'Baho yangilandi' : "Baho qo'yildi",
  )

  const isValid = (value: string, max: number) => {
    const number = Number(value)
    return value.trim() !== '' && Number.isInteger(number) && number >= 0 && number <= max
  }
  const scoreValid = useRubric
    ? criteria.every((item, index) => isValid(criterionScores[index], item.points))
    : isValid(score, MAX_SCORE)
  const rubricSum = criterionScores.reduce((sum, value) => sum + (Number(value) || 0), 0)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
      {useRubric ? (
        <fieldset className="grid gap-2">
          <legend className="mb-1 text-sm font-medium">Rubrika bo'yicha ballar</legend>
          {criteria.map((item, index) => (
            <div key={index} className="flex items-center justify-between gap-3">
              <label htmlFor={`criterion_${index}`} className="min-w-0 text-sm">
                {item.name}
                {item.description ? <span className="block text-xs text-muted-foreground">{item.description}</span> : null}
              </label>
              <div className="flex shrink-0 items-center gap-1.5">
                <Input
                  id={`criterion_${index}`}
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={item.points}
                  step={1}
                  className="h-9 w-20"
                  disabled={disabled}
                  aria-invalid={criterionScores[index] !== '' && !isValid(criterionScores[index], item.points)}
                  value={criterionScores[index]}
                  onChange={(event) =>
                    setCriterionScores((current) => current.map((value, i) => (i === index ? event.target.value : value)))
                  }
                />
                <span className="w-10 text-xs text-muted-foreground tabular-nums">/ {item.points}</span>
              </div>
            </div>
          ))}
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-t pt-2 text-sm">
            <span className="font-medium tabular-nums">
              Jami: {rubricSum} / {maxScore}
            </span>
            {suggested != null ? (
              <span className="text-xs text-muted-foreground">
                AI taklifi: {Math.round((suggested * maxScore) / MAX_SCORE)} / {maxScore}
              </span>
            ) : null}
          </div>
          {errors.rubric_scores ? (
            <p className="text-xs text-destructive" role="alert">
              {errors.rubric_scores}
            </p>
          ) : null}
        </fieldset>
      ) : (
      <FormField id="score" label={`Ball (0–${MAX_SCORE})`} error={errors.score}>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            id="score"
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_SCORE}
            step={1}
            className="h-10 w-28"
            disabled={disabled}
            aria-invalid={Boolean(errors.score)}
            value={score}
            onChange={(event) => setScore(event.target.value)}
          />
          {suggested != null && !disabled ? (
            <Button type="button" variant="outline" size="lg" onClick={() => setScore(String(suggested))}>
              AI taklifi: {suggested}
            </Button>
          ) : null}
        </div>
      </FormField>
      )}
      <FormField id="grade_comment" label="Izoh" error={errors.comment} hint="Ixtiyoriy. Talabaga ko'rinadi.">
        <Textarea
          id="grade_comment"
          className="max-h-48 min-h-20"
          disabled={disabled}
          aria-invalid={Boolean(errors.comment)}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
      </FormField>
      <Button type="submit" size="lg" className="justify-self-start" disabled={disabled || mutation.isPending || !scoreValid}>
        {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
        {submission.grade ? 'Bahoni yangilash' : "Baho qo'yish"}
      </Button>
    </form>
  )
}

function ReturnForm({ submission, disabled }: { submission: Submission; disabled: boolean }) {
  const [comment, setComment] = useState('')
  const { mutation, errors } = useReviewMutation(
    submission,
    () => api<Submission>(`/submissions/${submission.id}/return/`, { method: 'POST', body: { comment } }),
    'Yechim qayta ishlashga qaytarildi',
  )

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
      <FormField id="return_comment" label="Qaytarish sababi" error={errors.comment} hint="Talabaga ko'rinadi.">
        <Textarea
          id="return_comment"
          className="max-h-48 min-h-20"
          disabled={disabled}
          aria-invalid={Boolean(errors.comment)}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
      </FormField>
      <Button
        type="submit"
        variant="outline"
        size="lg"
        className="justify-self-start"
        disabled={disabled || mutation.isPending || !comment.trim()}
      >
        {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Undo2 aria-hidden="true" />}
        Qayta ishlashga qaytarish
      </Button>
    </form>
  )
}

function Review({ submission }: { submission: Submission }) {
  const assignment = useQuery({
    queryKey: ['assignment', submission.assignment],
    queryFn: () => api<Assignment>(`/assignments/${submission.assignment}/`),
  })
  const attempts = useQuery({
    queryKey: ['submissions', submission.assignment, 'student', submission.student.id],
    queryFn: () =>
      api<Submission[]>(`/assignments/${submission.assignment}/submissions/?student=${submission.student.id}`),
  })

  // Bosqichli loyihada urinishlar bosqich bo'yicha alohida
  const stageAttempts = attempts.data?.filter((attempt) => attempt.stage === submission.stage)
  const stage = assignment.data?.stages.find((item) => item.id === submission.stage) ?? null
  const criteria = assignment.data
    ? assignment.data.rubric.filter((item) => item.stage === (stage ? stage.order : null))
    : null
  // Backend faqat oxirgi urinishni baholashga ruxsat beradi
  const latestId = stageAttempts?.at(0)?.id
  const isLatest = latestId === undefined || latestId === submission.id
  const returned = submission.status === 'returned'

  return (
    <>
      <Link
        to={`/assignments/${submission.assignment}`}
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        {assignment.data?.title ?? 'Topshiriq'}
      </Link>
      <PageHeader
        title={fullName(submission.student)}
        description={`${stage ? `${stage.order + 1}-bosqich: ${stage.title} · ` : ''}${submission.attempt_number}-urinish · ${formatDateTime(submission.submitted_at)}`}
        actions={<SubmissionStatusBadge submission={submission} />}
      />

      {stageAttempts && stageAttempts.length > 1 ? (
        <nav className="mb-4 flex flex-wrap gap-2" aria-label="Urinishlar">
          {[...stageAttempts].reverse().map((attempt) => (
            <Link
              key={attempt.id}
              to={`/submissions/${attempt.id}`}
              aria-current={attempt.id === submission.id ? 'page' : undefined}
              className={cn(
                'rounded-lg border px-3 py-1.5 text-sm transition-colors',
                attempt.id === submission.id
                  ? 'border-primary bg-primary/10 font-medium text-primary'
                  : 'bg-background text-muted-foreground hover:bg-muted',
              )}
            >
              {attempt.attempt_number}-urinish
            </Link>
          ))}
        </nav>
      ) : null}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{submission.diagram ? 'ER-diagramma' : 'SQL kod'}</CardTitle>
            </CardHeader>
            <CardContent>
              {submission.diagram ? <ErEditor value={submission.diagram} /> : <SqlCode code={submission.sql_code} />}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>AI tahlili</CardTitle>
            </CardHeader>
            <CardContent>
              <AnalysisPanel submissionId={submission.id} staff />
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4">
          {!isLatest ? (
            <Alert>
              <AlertTitle>Bu eski urinish</AlertTitle>
              <AlertDescription>Faqat talabaning oxirgi urinishini baholash yoki qaytarish mumkin.</AlertDescription>
            </Alert>
          ) : null}
          {returned ? (
            <Alert>
              <AlertTitle>Qayta ishlashga qaytarilgan</AlertTitle>
              <AlertDescription className="whitespace-pre-wrap">{submission.return_comment}</AlertDescription>
            </Alert>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>Baho</CardTitle>
              <CardDescription>
                {submission.grade
                  ? `${submission.grade.graded_by ? fullName(submission.grade.graded_by) : 'Noma\'lum'} · ${formatDateTime(submission.grade.updated_at)}`
                  : 'Yakuniy bahoni siz qo\'yasiz; AI bahosi faqat taklif.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {criteria ? (
                <GradeForm key={submission.id} submission={submission} criteria={criteria} disabled={!isLatest} />
              ) : (
                <ListSkeleton rows={1} />
              )}
            </CardContent>
          </Card>
          {returned ? null : (
            <Card>
              <CardHeader>
                <CardTitle>Qayta ishlashga qaytarish</CardTitle>
                <CardDescription>Talaba izohingizni ko'rib, yangi urinish topshira oladi.</CardDescription>
              </CardHeader>
              <CardContent>
                <ReturnForm submission={submission} disabled={!isLatest} />
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}

export function SubmissionPage() {
  const params = useParams()
  const id = Number(params.id)
  const validId = Number.isInteger(id) && id > 0

  const submission = useQuery({
    queryKey: ['submission', id],
    queryFn: () => api<Submission>(`/submissions/${id}/`),
    enabled: validId,
  })

  if (!validId) return <NotFoundPage />
  if (submission.isPending) return <ListSkeleton />
  if (submission.isError) {
    if (submission.error instanceof ApiError && submission.error.status === 404) return <NotFoundPage />
    return <ErrorState error={submission.error} onRetry={() => void submission.refetch()} />
  }
  // key: boshqa urinishga o'tilganda forma holati tozalanadi
  return <Review key={`${submission.data.id}-${submission.data.status}`} submission={submission.data} />
}
