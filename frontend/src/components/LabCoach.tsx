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
import { cleanDiagram } from '@/lib/er'
import type { ErDiagram, LabChatState } from '@/lib/types'

const MAX_QUESTION_LENGTH = 2000

export interface LabWork {
  code?: string
  diagram?: ErDiagram | null
}

/** Laboratoriya murabbiyi: savol bilan birga talabaning hozirgi kodi yoki diagrammasi ham yuboriladi. */
export function LabCoach({ labId, getWork }: { labId: number; getWork: () => LabWork }) {
  const queryClient = useQueryClient()
  const queryKey = ['lab-chat', labId]
  const [draft, setDraft] = useState('')
  const listEnd = useRef<HTMLDivElement>(null)

  const chat = useQuery({ queryKey, queryFn: () => api<LabChatState>(`/labs/${labId}/chat/`) })
  const send = useMutation({
    mutationFn: (content: string) => {
      const work = getWork()
      const body: Record<string, unknown> = { content }
      if (work.diagram?.entities.length) body.diagram = cleanDiagram(work.diagram)
      else if (work.code?.trim()) body.sql_code = work.code
      return api<LabChatState>(`/labs/${labId}/chat/`, { method: 'POST', body })
    },
    onSuccess: (state) => {
      queryClient.setQueryData(queryKey, state)
      setDraft('')
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  const messageCount = chat.data?.messages.length ?? 0
  useEffect(() => {
    listEnd.current?.scrollIntoView({ block: 'nearest' })
  }, [messageCount, send.isPending])

  if (chat.isPending) return <Skeleton className="h-32 w-full" />
  if (chat.isError) return <ErrorState error={chat.error} onRetry={() => void chat.refetch()} />

  const limitReached = chat.data.ai_left <= 0
  const canSend = Boolean(draft.trim()) && !send.isPending && !limitReached

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
    <div className="grid gap-3">
      <div className="grid max-h-96 min-h-32 content-start gap-2 overflow-y-auto rounded-lg border p-3" aria-live="polite">
        {chat.data.messages.length || send.isPending ? null : (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Qayerda qiynalayotganingizni yozing. Murabbiy javobni aytmaydi: savollar bilan o'zingiz topishingizga yordam
            beradi va kurs materiallariga tayanadi. Savol bilan birga hozirgi ishingiz ham yuboriladi.
          </p>
        )}
        {chat.data.messages.map((message) => (
          <Bubble key={message.id} role={message.role}>
            {message.content}
          </Bubble>
        ))}
        {send.isPending ? (
          <>
            <Bubble role="user">{send.variables}</Bubble>
            <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Murabbiy o'ylamoqda…
            </div>
          </>
        ) : null}
        <div ref={listEnd} />
      </div>
      <form onSubmit={handleSubmit} className="grid gap-2">
        <div className="flex items-end gap-2">
          <Textarea
            aria-label="Murabbiyga savol"
            className="max-h-40 min-h-10"
            placeholder={limitReached ? 'Bugungi AI limiti tugadi' : 'Masalan: bu bog\'lanish 1:N mi yoki M:N?'}
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
        <p className="text-xs text-muted-foreground">
          Bugun yana {chat.data.ai_left} ta AI yordami qoldi (maslahatlar va murabbiy umumiy limitda).
        </p>
      </form>
    </div>
  )
}
