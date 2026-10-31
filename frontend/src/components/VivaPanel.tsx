import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GraduationCap, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import type { Viva } from '@/lib/types'
import { cn } from '@/lib/utils'

const SCORE_STYLES = [
  'bg-red-100 text-red-900',
  'bg-amber-100 text-amber-900',
  'bg-emerald-100 text-emerald-900',
]

function AnswersForm({ submissionId, viva }: { submissionId: number; viva: Viva }) {
  const queryClient = useQueryClient()
  const [answers, setAnswers] = useState<string[]>(viva.questions.map(() => ''))
  const mutation = useMutation({
    mutationFn: () =>
      api<{ viva: Viva }>(`/submissions/${submissionId}/viva/answers/`, { method: 'POST', body: { answers } }),
    onSuccess: (data) => queryClient.setQueryData(['viva', submissionId], data),
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      {viva.questions.map((question, index) => (
        <div key={index} className="grid gap-1.5">
          <label htmlFor={`viva-${index}`} className="text-sm font-medium">
            {index + 1}. {question}
          </label>
          <Textarea
            id={`viva-${index}`}
            className="min-h-20"
            maxLength={2000}
            value={answers[index]}
            onChange={(event) =>
              setAnswers((current) => current.map((item, position) => (position === index ? event.target.value : item)))
            }
          />
        </div>
      ))}
      <Button type="submit" className="justify-self-start" disabled={mutation.isPending || !answers.some((item) => item.trim())}>
        {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
        {mutation.isPending ? 'Baholanmoqda…' : 'Javoblarni topshirish'}
      </Button>
      <p className="text-xs text-muted-foreground">Javoblar bir marta topshiriladi. O'z so'zlaringiz bilan yozing.</p>
    </form>
  )
}

function Results({ viva, staff }: { viva: Viva; staff: boolean }) {
  return (
    <div className="grid gap-3">
      {staff && viva.understanding !== undefined && viva.understanding !== null ? (
        <div className="rounded-lg border bg-muted/40 p-3 text-sm">
          <div className="font-medium">Tushunish darajasi: {viva.understanding}%</div>
          {viva.teacher_summary ? <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{viva.teacher_summary}</p> : null}
          <p className="mt-1 text-xs text-muted-foreground">
            AI bahosi — taxmin. Shubha bo'lsa, talaba bilan og'zaki suhbatlashing; bahoni o'zingiz qo'yasiz.
          </p>
        </div>
      ) : null}
      <ol className="grid gap-3">
        {viva.questions.map((question, index) => {
          const item = viva.feedback[index]
          return (
            <li key={index} className="grid gap-1 text-sm">
              <div className="font-medium">
                {index + 1}. {question}
              </div>
              <p className="whitespace-pre-wrap text-muted-foreground">{viva.answers[index] || '(javob yozilmagan)'}</p>
              {item ? (
                <p className="flex flex-wrap items-baseline gap-2">
                  <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', SCORE_STYLES[item.score])}>
                    {item.score} / 2
                  </span>
                  <span className="whitespace-pre-wrap">{item.comment}</span>
                </p>
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

/** Loyiha himoyasi: AI talabaning o'z yechimi bo'yicha 5 ta savol beradi va javoblarni baholaydi. */
export function VivaPanel({ submissionId, staff = false }: { submissionId: number; staff?: boolean }) {
  const queryClient = useQueryClient()
  const viva = useQuery({
    queryKey: ['viva', submissionId],
    queryFn: () => api<{ viva: Viva | null }>(`/submissions/${submissionId}/viva/`),
  })
  const start = useMutation({
    mutationFn: () => api<{ viva: Viva }>(`/submissions/${submissionId}/viva/`, { method: 'POST' }),
    onSuccess: (data) => queryClient.setQueryData(['viva', submissionId], data),
    onError: (error) => toast.error(errorMessage(error)),
  })

  if (viva.isPending) return <Skeleton className="h-20 w-full" />
  if (viva.isError) return <ErrorState error={viva.error} onRetry={() => void viva.refetch()} />
  const session = viva.data.viva

  if (!session) {
    if (staff) return <p className="text-sm text-muted-foreground">Talaba bu yechim bo'yicha hali himoyadan o'tmagan.</p>
    return (
      <div className="grid gap-2">
        <p className="text-sm text-muted-foreground">
          AI aynan sizning yechimingiz bo'yicha 5 ta savol beradi: nega shunday loyihaladingiz, nima o'zgarsa nima
          bo'ladi. Javoblaringiz va AI izohi o'qituvchiga ko'rinadi.
        </p>
        <Button type="button" variant="outline" className="justify-self-start" disabled={start.isPending} onClick={() => start.mutate()}>
          {start.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <GraduationCap aria-hidden="true" />}
          {start.isPending ? 'Savollar tuzilmoqda…' : 'Himoyani boshlash'}
        </Button>
      </div>
    )
  }
  if (session.status === 'asked') {
    if (staff) return <p className="text-sm text-muted-foreground">Talaba savollarni oldi, lekin hali javob bermadi.</p>
    return <AnswersForm submissionId={submissionId} viva={session} />
  }
  return <Results viva={session} staff={staff} />
}
