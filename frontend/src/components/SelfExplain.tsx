import { useMutation } from '@tanstack/react-query'
import { Loader2, MessageSquareText } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage, fieldErrors } from '@/lib/api'
import { EXPLANATION_VERDICTS, type ExplanationVerdict } from '@/lib/types'
import { cn } from '@/lib/utils'

const MIN_LENGTH = 40

export function VerdictBadge({ verdict }: { verdict: ExplanationVerdict }) {
  const { label, className } = EXPLANATION_VERDICTS[verdict]
  return <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', className)}>{label}</span>
}

/** To'g'ri yechimdan keyin: talaba yechimini o'z so'zlari bilan tushuntiradi, AI mosligini baholaydi. */
export function SelfExplain({ attemptId, kind }: { attemptId: number; kind: 'sql' | 'er' }) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: () =>
      api<{ verdict: ExplanationVerdict; feedback: string }>(`/labs/attempts/${attemptId}/explain/`, {
        method: 'POST',
        body: { text },
      }),
    onError: (failure) => {
      const message = fieldErrors(failure).text
      if (message) setError(message)
      else toast.error(errorMessage(failure))
    },
  })

  return (
    <div className="grid gap-2 rounded-lg border bg-background p-3 text-foreground">
      <div className="flex items-center gap-1.5 text-sm font-medium">
        <MessageSquareText className="size-4" aria-hidden="true" />
        Yechimingizni o'z so'zlaringiz bilan tushuntiring
      </div>
      <p className="text-xs text-muted-foreground">
        {kind === 'er'
          ? "Nega bog'lanishlar va kardinallik aynan shunday? Qaysi atribut nima uchun kalit?"
          : 'Kodingiz nima qiladi va nega shunday yozdingiz (qaysi jadval, qaysi shart, nega shu tartibda)?'}{' '}
        Bahoga ta'sir qilmaydi, lekin o'qituvchi ko'radi: tushunib yechganingizni shu ko'rsatadi.
      </p>
      <Textarea
        aria-label="Tushuntirish"
        className="min-h-24"
        maxLength={3000}
        value={text}
        aria-invalid={Boolean(error)}
        onChange={(event) => {
          setText(event.target.value)
          setError(null)
        }}
      />
      {error ? (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <Button
        type="button"
        variant="outline"
        className="justify-self-start"
        disabled={mutation.isPending || text.trim().length < MIN_LENGTH}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
        Tushuntirishni tekshirish
      </Button>
      {mutation.data ? (
        <div className="grid gap-1 text-sm" aria-live="polite">
          <VerdictBadge verdict={mutation.data.verdict} />
          <p className="whitespace-pre-wrap">{mutation.data.feedback}</p>
        </div>
      ) : null}
    </div>
  )
}
