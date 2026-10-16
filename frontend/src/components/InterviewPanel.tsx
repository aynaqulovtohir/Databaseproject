import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, SendHorizontal } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { toast } from 'sonner'

import { Bubble } from '@/components/ChatPanel'
import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import type { InterviewRequirement, InterviewState } from '@/lib/types'

const MAX_QUESTION_LENGTH = 1000

const REQUIREMENT_KINDS: Record<InterviewRequirement['kind'], string> = {
  entity: 'Obyektlar',
  attribute: 'Saqlanadigan ma\'lumotlar',
  relationship: 'Bog\'lanishlar',
  rule: 'Biznes qoidalari',
}

/** Talablar turlari bo'yicha guruhlangan ro'yxat (talabaning yozuvlari) */
export function RequirementList({ items, muted = false }: { items: InterviewRequirement[]; muted?: boolean }) {
  const kinds = (Object.keys(REQUIREMENT_KINDS) as InterviewRequirement['kind'][]).filter((kind) =>
    items.some((item) => item.kind === kind),
  )
  return (
    <div className="grid gap-3">
      {kinds.map((kind) => (
        <div key={kind} className="grid gap-1">
          <h4 className="text-xs font-medium text-muted-foreground">{REQUIREMENT_KINDS[kind]}</h4>
          <ul className={muted ? 'grid list-disc gap-1 pl-5 text-sm text-muted-foreground' : 'grid list-disc gap-1 pl-5 text-sm'}>
            {items
              .filter((item) => item.kind === kind)
              .map((item) => (
                <li key={item.id}>{item.text}</li>
              ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

/** Talablarni aniqlash: AI-buyurtmachi bilan suhbat va aniqlangan talablar */
export function InterviewPanel({ labId }: { labId: number }) {
  const queryClient = useQueryClient()
  const queryKey = ['lab-interview', labId]
  const [draft, setDraft] = useState('')
  const listEnd = useRef<HTMLDivElement>(null)

  const interview = useQuery({ queryKey, queryFn: () => api<InterviewState>(`/labs/${labId}/interview/`) })
  const send = useMutation({
    mutationFn: (content: string) => api<InterviewState>(`/labs/${labId}/interview/`, { method: 'POST', body: { content } }),
    onSuccess: (state) => {
      queryClient.setQueryData(queryKey, state)
      setDraft('')
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  const messageCount = interview.data?.messages.length ?? 0
  useEffect(() => {
    listEnd.current?.scrollIntoView({ block: 'nearest' })
  }, [messageCount, send.isPending])

  if (interview.isPending) return <Skeleton className="h-48 w-full" />
  if (interview.isError) return <ErrorState error={interview.error} onRetry={() => void interview.refetch()} />

  const data = interview.data
  const limitReached = data.questions_left <= 0
  const canSend = Boolean(draft.trim()) && !send.isPending && !limitReached
  const percent = data.total ? Math.round((100 * data.found.length) / data.total) : 0

  function submit() {
    if (canSend) send.mutate(draft.trim())
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div className="grid gap-3">
        <div className="grid max-h-[28rem] min-h-48 content-start gap-2 overflow-y-auto rounded-lg border p-3" aria-live="polite">
          {data.messages.length || send.isPending ? null : (
            <p className="py-4 text-center text-sm text-muted-foreground">
              Buyurtmachi bilan tanishing va savol bering. Masalan: «Kimlar yoki nimalar haqida ma'lumot saqlash kerak?»
            </p>
          )}
          {data.messages.map((message) => (
            <Bubble key={message.id} role={message.role}>
              {message.content}
            </Bubble>
          ))}
          {send.isPending ? (
            <>
              <Bubble role="user">{send.variables}</Bubble>
              <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                Buyurtmachi javob yozmoqda…
              </div>
            </>
          ) : null}
          <div ref={listEnd} />
        </div>
        <form onSubmit={handleSubmit} className="grid gap-2">
          <div className="flex items-end gap-2">
            <Textarea
              aria-label="Buyurtmachiga savol"
              className="max-h-40 min-h-10"
              placeholder={limitReached ? 'Savollar soni tugadi' : "Masalan: bitta shifokor nechta bo'limda ishlaydi?"}
              maxLength={MAX_QUESTION_LENGTH}
              disabled={limitReached}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
            />
            <Button type="submit" size="icon-lg" className="size-10" aria-label="Yuborish" disabled={!canSend}>
              <SendHorizontal />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">Bu laboratoriyada yana {data.questions_left} ta savol berish mumkin.</p>
        </form>
      </div>

      <section className="grid gap-3 rounded-lg border p-3" aria-labelledby={`interview-found-${labId}`}>
        <div className="grid gap-1.5">
          <div className="flex items-baseline justify-between gap-2">
            <h3 id={`interview-found-${labId}`} className="text-sm font-medium">
              Aniqlangan talablar
            </h3>
            <span className="text-sm tabular-nums">
              {data.found.length} / {data.total}
            </span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={data.total}
            aria-valuenow={data.found.length}
            aria-label="Aniqlangan talablar"
          >
            <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
          </div>
        </div>
        {data.found.length ? (
          <RequirementList items={data.found} />
        ) : (
          <p className="text-sm text-muted-foreground">Buyurtmachi aytgan talablar shu yerda yig'iladi.</p>
        )}
        {data.missed?.length ? (
          <div className="grid gap-2 border-t pt-3">
            <h3 className="text-sm font-medium">Aniqlanmagan talablar</h3>
            <p className="text-xs text-muted-foreground">
              Laboratoriya yechilgandan keyin ko'rsatiladi: keyingi suhbatda qanday savol berish kerakligini o'ylab ko'ring.
            </p>
            <RequirementList items={data.missed} muted />
          </div>
        ) : null}
      </section>
    </div>
  )
}
