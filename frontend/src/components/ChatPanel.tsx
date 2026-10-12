import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, SendHorizontal } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import type { ChatReply, ChatState } from '@/lib/types'
import { cn } from '@/lib/utils'

const MAX_MESSAGE_LENGTH = 4000

function Bubble({ role, children }: { role: 'user' | 'assistant'; children: string }) {
  return (
    <div className={cn('flex', role === 'user' ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap',
          role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted',
        )}
      >
        {children}
      </div>
    </div>
  )
}

/** Talabaning shu topshiriq bo'yicha AI yordamchi bilan yozishmasi. */
export function ChatPanel({ assignmentId }: { assignmentId: number }) {
  const queryClient = useQueryClient()
  const queryKey = ['chat', assignmentId]
  const [draft, setDraft] = useState('')
  const listEnd = useRef<HTMLDivElement>(null)

  const chat = useQuery({ queryKey, queryFn: () => api<ChatState>(`/assignments/${assignmentId}/chat/`) })

  const send = useMutation({
    mutationFn: (content: string) =>
      api<ChatReply>(`/assignments/${assignmentId}/chat/`, { method: 'POST', body: { content } }),
    onSuccess: (reply) => {
      queryClient.setQueryData<ChatState>(queryKey, (current) => ({
        messages: [...(current?.messages ?? []), reply.question, reply.answer],
        daily_limit: reply.daily_limit,
        used_today: reply.used_today,
      }))
      setDraft('')
    },
    // Xato bo'lsa, yozilgan savol maydonda qoladi
    onError: (error) => toast.error(errorMessage(error)),
  })

  const messageCount = chat.data?.messages.length ?? 0
  useEffect(() => {
    listEnd.current?.scrollIntoView({ block: 'nearest' })
  }, [messageCount, send.isPending])

  if (chat.isPending) return <Skeleton className="h-40 w-full" />
  if (chat.isError) return <ErrorState error={chat.error} onRetry={() => void chat.refetch()} />

  const { messages, daily_limit: dailyLimit, used_today: usedToday } = chat.data
  const limitReached = usedToday >= dailyLimit
  const canSend = Boolean(draft.trim()) && !send.isPending && !limitReached

  function submit() {
    if (canSend) send.mutate(draft.trim())
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter — yuborish, Shift+Enter — yangi qator
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="grid gap-3">
      <div className="grid max-h-[28rem] min-h-40 content-start gap-2 overflow-y-auto rounded-lg border p-3" aria-live="polite">
        {messages.length || send.isPending ? null : (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Topshiriq bo'yicha savol bering. Yordamchi tayyor yechimni yozib bermaydi, lekin tushuntirib, yo'l
            ko'rsatadi.
          </p>
        )}
        {messages.map((message) => (
          <Bubble key={message.id} role={message.role}>
            {message.content}
          </Bubble>
        ))}
        {send.isPending ? (
          <>
            <Bubble role="user">{send.variables}</Bubble>
            <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              Yordamchi javob yozmoqda…
            </div>
          </>
        ) : null}
        <div ref={listEnd} />
      </div>

      <form onSubmit={handleSubmit} className="grid gap-2">
        <div className="flex items-end gap-2">
          <Textarea
            aria-label="Savolingiz"
            className="max-h-40 min-h-10"
            placeholder={limitReached ? 'Bugungi limit tugadi' : 'Savolingizni yozing…'}
            maxLength={MAX_MESSAGE_LENGTH}
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
          Bugun {usedToday} / {dailyLimit} ta xabar ishlatildi.
          {limitReached ? ' Limit tugadi, ertaga davom etishingiz mumkin.' : null}
        </p>
      </form>
    </div>
  )
}
