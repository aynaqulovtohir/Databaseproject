import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Send, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { ErEditor } from '@/components/ErEditor'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { PeerCriterionKey, PeerReviewReceived, PeerReviewState } from '@/lib/types'

const MIN_COMMENT = 20
const MAX_COMMENT = 2000

/** Bitta mezon: 1-4 ball tugmalari (bosilgan holati aria-pressed bilan) */
function CriterionRow({
  name,
  hint,
  scale,
  value,
  onChange,
}: {
  name: string
  hint: string
  scale: PeerReviewState['scale']
  value: number | undefined
  onChange: (value: number) => void
}) {
  const labelId = useId()
  return (
    <div className="grid gap-1.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div>
        <div id={labelId} className="text-sm font-medium">
          {name}
        </div>
        <div className="text-xs text-muted-foreground">{hint}</div>
      </div>
      <div role="group" aria-labelledby={labelId} className="inline-flex w-fit rounded-lg border p-0.5">
        {scale.map((item) => (
          <button
            key={item.value}
            type="button"
            aria-pressed={value === item.value}
            aria-label={`${item.value} — ${item.label}`}
            title={item.label}
            className={cn(
              'size-8 rounded-md text-sm tabular-nums transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
              value === item.value ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
            )}
            onClick={() => onChange(item.value)}
          >
            {item.value}
          </button>
        ))}
      </div>
    </div>
  )
}

function ReviewForm({ labId, state }: { labId: number; state: PeerReviewState }) {
  const queryClient = useQueryClient()
  const current = state.current!
  const [scores, setScores] = useState<Partial<Record<PeerCriterionKey, number>>>({})
  const [comment, setComment] = useState('')
  const send = useMutation({
    mutationFn: () =>
      api<PeerReviewState>(`/labs/${labId}/peer-review/`, {
        method: 'POST',
        body: { attempt: current.attempt_id, scores, comment },
      }),
    onSuccess: (next) => {
      queryClient.setQueryData(['peer-review', labId], next)
      setScores({})
      setComment('')
      toast.success('Baholash yuborildi. Rahmat!')
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const complete = state.criteria.every((criterion) => scores[criterion.key])
  const commentOk = comment.trim().length >= MIN_COMMENT
  const canSend = complete && commentOk && !send.isPending

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (canSend) send.mutate()
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4">
      <ErEditor key={current.attempt_id} value={current.diagram} />
      <div className="grid gap-3">
        {state.criteria.map((criterion) => (
          <CriterionRow
            key={criterion.key}
            name={criterion.name}
            hint={criterion.hint}
            scale={state.scale}
            value={scores[criterion.key]}
            onChange={(value) => setScores((previous) => ({ ...previous, [criterion.key]: value }))}
          />
        ))}
        <p className="text-xs text-muted-foreground">
          {state.scale.map((item) => `${item.value} — ${item.label.toLowerCase()}`).join(' · ')}
        </p>
      </div>
      <div className="grid gap-1.5">
        <label htmlFor={`peer-comment-${labId}`} className="text-sm font-medium">
          Izoh
        </label>
        <Textarea
          id={`peer-comment-${labId}`}
          className="min-h-24"
          maxLength={MAX_COMMENT}
          placeholder="Nima yaxshi chiqqan? Nimani tuzatish yoki yaxshilash mumkin? Hurmat bilan va aniq yozing."
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
        <p className="text-xs text-muted-foreground tabular-nums">
          {commentOk ? `${comment.trim().length} belgi` : `Kamida ${MIN_COMMENT} belgi (${comment.trim().length} / ${MIN_COMMENT})`}
        </p>
      </div>
      <Button type="submit" size="lg" className="w-fit" disabled={!canSend}>
        {send.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
        Baholashni yuborish
      </Button>
    </form>
  )
}

function ReceivedReview({ labId, review, state }: { labId: number; review: PeerReviewReceived; state: PeerReviewState }) {
  const queryClient = useQueryClient()
  const mark = useMutation({
    mutationFn: (helpful: boolean) =>
      api<{ id: number; helpful: boolean }>(`/labs/peer-reviews/${review.id}/helpful/`, { method: 'POST', body: { helpful } }),
    onSuccess: ({ helpful }) =>
      queryClient.setQueryData<PeerReviewState>(['peer-review', labId], (previous) =>
        previous
          ? { ...previous, received: previous.received.map((item) => (item.id === review.id ? { ...item, helpful } : item)) }
          : previous,
      ),
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <li className="grid gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums">
        {state.criteria.map((criterion) => (
          <span key={criterion.key}>
            {criterion.name}: <span className="text-foreground">{review.scores[criterion.key]}</span> / 4
          </span>
        ))}
        <span className="ml-auto">{formatDateTime(review.created_at)}</span>
      </div>
      <p className="text-sm whitespace-pre-wrap">{review.comment}</p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">Bu izoh sizga foydali bo'ldimi?</span>
        <Button
          type="button"
          size="sm"
          variant={review.helpful === true ? 'secondary' : 'ghost'}
          aria-pressed={review.helpful === true}
          disabled={mark.isPending}
          onClick={() => mark.mutate(true)}
        >
          <ThumbsUp aria-hidden="true" />
          Foydali
        </Button>
        <Button
          type="button"
          size="sm"
          variant={review.helpful === false ? 'secondary' : 'ghost'}
          aria-pressed={review.helpful === false}
          disabled={mark.isPending}
          onClick={() => mark.mutate(false)}
        >
          <ThumbsDown aria-hidden="true" />
          Foydali emas
        </Button>
      </div>
    </li>
  )
}

/** O'zaro baholash: guruhdoshlarning ishini baholash va o'z ishiga berilgan baholar */
export function PeerReviewPanel({ labId }: { labId: number }) {
  const state = useQuery({
    queryKey: ['peer-review', labId],
    queryFn: () => api<PeerReviewState>(`/labs/${labId}/peer-review/`),
  })
  if (state.isPending) return <Skeleton className="h-32 w-full" />
  if (state.isError) return <ErrorState error={state.error} onRetry={() => void state.refetch()} />
  const data = state.data
  return (
    <div className="grid gap-6">
      <section className="grid gap-3">
        <h3 className="flex items-baseline justify-between gap-2 text-sm font-medium">
          Guruhdoshingiz ishini baholang
          <span className="font-normal text-muted-foreground tabular-nums">
            {data.written} / {data.per_lab}
          </span>
        </h3>
        {data.current ? (
          <ReviewForm key={data.current.attempt_id} labId={labId} state={data} />
        ) : (
          <p className="text-sm text-muted-foreground">{data.reason}</p>
        )}
      </section>
      <section className="grid gap-3 border-t pt-4">
        <h3 className="text-sm font-medium">Sizning ishingizga berilgan baholar</h3>
        {data.received.length ? (
          <ul className="grid gap-3">
            {data.received.map((review) => (
              <ReceivedReview key={review.id} labId={labId} review={review} state={data} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            Baholashga topshirgan diagrammangizni guruhdoshlaringiz baholagach, ularning izohlari shu yerda chiqadi.
          </p>
        )}
      </section>
    </div>
  )
}
