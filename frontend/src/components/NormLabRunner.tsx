import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, Loader2, Search, Send } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfidencePicker } from '@/components/ConfidencePicker'
import { FormField } from '@/components/FormField'
import { AiAdvice, GradeCard } from '@/components/LabRunner'
import { SelfExplain } from '@/components/SelfExplain'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage, fieldErrors } from '@/lib/api'
import { useConfidence } from '@/lib/confidence'
import type { LabRunResult, NormAnswer, NormalForm, NormTask } from '@/lib/types'

const FORMS: NormalForm[] = ['1NF', '2NF', '3NF', 'BCNF']
const INPUT_PROPS = { spellCheck: false, autoCapitalize: 'none', autoCorrect: 'off' } as const

function lines(value: NormAnswer['keys'] | undefined) {
  return (value ?? []).map((item) => (Array.isArray(item) ? item.join(', ') : item)).join('\n')
}

function splitLines(text: string) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

/** Topshiriqning o'zi: munosabat va funksional bog'liqliklar */
export function NormTaskView({ task }: { task: NormTask }) {
  return (
    <div className="grid gap-2 rounded-lg border bg-muted/30 p-3 font-mono text-sm">
      <div className="break-words">R({task.attributes.join(', ')})</div>
      <ul className="grid gap-0.5">
        {task.fds.map((fd, index) => (
          <li key={index}>
            {fd.lhs.join(', ')} → {fd.rhs.join(', ')}
          </li>
        ))}
      </ul>
      <div className="font-sans text-xs text-muted-foreground">Maqsad: {task.target}</div>
    </div>
  )
}

interface NormLabRunnerProps {
  labId: number
  task: NormTask
  initialAnswer?: NormAnswer | null
  gradable?: boolean
  onResult?: (result: LabRunResult, answerText: string) => void
  /** Javob matni o'zgarganda (murabbiyga hozirgi ishni yuborish uchun) */
  onAnswerChange?: (answerText: string) => void
}

/** Normallashtirish javobi: kalitlar, hozirgi normal forma va dekompozitsiya. Tekshiruv algoritmik. */
export function NormLabRunner({ labId, task, initialAnswer, gradable = false, onResult, onAnswerChange }: NormLabRunnerProps) {
  const [keys, setKeys] = useState(lines(initialAnswer?.keys))
  const [form, setForm] = useState<NormalForm | ''>(initialAnswer?.normal_form ?? '')
  const [decomposition, setDecomposition] = useState(lines(initialAnswer?.decomposition))
  const [error, setError] = useState<string | null>(null)
  const confidence = useConfidence()

  function summary(next: { keys?: string; form?: string; decomposition?: string }) {
    return `Kalitlar:\n${next.keys ?? keys}\nNormal forma: ${next.form ?? form}\nDekompozitsiya:\n${next.decomposition ?? decomposition}`
  }

  const mutation = useMutation({
    mutationFn: ({ mode, level }: { mode: 'run' | 'submit'; level: number | null }) =>
      api<LabRunResult>(`/labs/${labId}/${mode}/`, {
        method: 'POST',
        body: {
          answer: { keys: splitLines(keys), normal_form: form, decomposition: splitLines(decomposition) },
          ...confidence.body(level),
        },
      }),
    onSuccess: (result, { level }) => {
      if (gradable) confidence.record(level, result.is_correct)
      onResult?.(result, summary({}))
    },
    onError: (failure) => {
      const message = fieldErrors(failure).answer
      if (message) setError(message)
      else toast.error(errorMessage(failure))
    },
  })

  const canRun = !mutation.isPending && Boolean(keys.trim() && form && decomposition.trim())
  const result = mutation.data
  const submitting = mutation.isPending && mutation.variables?.mode === 'submit'
  const run = (mode: 'run' | 'submit') => mutation.mutate({ mode, level: gradable ? confidence.value : null })

  return (
    <div className="grid gap-4">
      <NormTaskView task={task} />
      <FormField id="norm_keys" label="Nomzod kalitlar" hint="Har bir qatorda bitta kalit, atributlar vergul bilan: talaba_id, fan_id">
        <Textarea
          id="norm_keys"
          className="min-h-16 font-mono text-sm md:text-xs"
          value={keys}
          onChange={(event) => {
            setKeys(event.target.value)
            setError(null)
            onAnswerChange?.(summary({ keys: event.target.value }))
          }}
          {...INPUT_PROPS}
        />
      </FormField>
      <FormField id="norm_form" label="Munosabatning hozirgi normal formasi">
        <select
          id="norm_form"
          className="h-10 justify-self-start rounded-md border bg-background px-2 text-sm"
          value={form}
          onChange={(event) => {
            setForm(event.target.value as NormalForm)
            setError(null)
            onAnswerChange?.(summary({ form: event.target.value }))
          }}
        >
          <option value="">Tanlang…</option>
          {FORMS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </FormField>
      <FormField
        id="norm_decomposition"
        label={`${task.target} dagi dekompozitsiya`}
        hint="Har bir qatorda bitta jadval: talaba(talaba_id, ism) yoki shunchaki talaba_id, ism"
      >
        <Textarea
          id="norm_decomposition"
          className="min-h-28 font-mono text-sm md:text-xs"
          value={decomposition}
          onChange={(event) => {
            setDecomposition(event.target.value)
            setError(null)
            onAnswerChange?.(summary({ decomposition: event.target.value }))
          }}
          {...INPUT_PROPS}
        />
      </FormField>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      {gradable ? <ConfidencePicker value={confidence.value} onChange={confidence.setValue} note={confidence.note} /> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button size="lg" variant={gradable ? 'outline' : 'default'} disabled={!canRun} onClick={() => run('run')}>
          {mutation.isPending && !submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Search aria-hidden="true" />}
          Tekshirish
        </Button>
        {gradable ? (
          <Button size="lg" disabled={!canRun} onClick={() => run('submit')}>
            {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
            Baholashga topshirish
          </Button>
        ) : null}
      </div>

      {result && !mutation.isPending ? (
        <div className="grid gap-4" aria-live="polite">
          {result.grade ? <GradeCard grade={result.grade} best={result.best_grade} /> : null}
          {result.is_correct ? (
            <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-emerald-900" role="status">
              <div className="flex items-center gap-2 font-medium">
                <CircleCheck className="size-5 shrink-0" aria-hidden="true" />
                To'g'ri!
              </div>
              <p className="mt-1 text-sm">Kalitlar, normal forma va dekompozitsiya to'g'ri.</p>
              {result.ai_explain && result.attempt_id ? (
                <div className="mt-3">
                  <SelfExplain attemptId={result.attempt_id} kind="sql" />
                </div>
              ) : null}
            </div>
          ) : (
            <div className="grid gap-3 rounded-lg border border-red-300 bg-red-50 p-3 text-red-900" role="alert">
              <div className="flex items-center gap-2 font-medium">
                <CircleX className="size-5 shrink-0" aria-hidden="true" />
                Javobda xatolar bor
              </div>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {result.differences.map((difference, index) => (
                  <li key={index}>{difference}</li>
                ))}
              </ul>
              {result.ai_available && result.attempt_id ? <AiAdvice attemptId={result.attempt_id} /> : null}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
