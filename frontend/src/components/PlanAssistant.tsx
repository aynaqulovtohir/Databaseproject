import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, Gauge, Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { SqlCode } from '@/components/SqlCode'
import { Button } from '@/components/ui/button'
import { api, errorMessage } from '@/lib/api'
import type { PlanExplanation, PlanMeasure, PlanSuggestion } from '@/lib/types'

function MeasureView({ title, measure }: { title: string; measure: PlanMeasure }) {
  return (
    <div className="grid min-w-0 gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 text-sm font-medium">
        {title}
        {measure.cost !== null ? (
          <span className="text-xs font-normal text-muted-foreground tabular-nums">narx: {measure.cost}</span>
        ) : null}
      </div>
      {measure.ok ? (
        <>
          <SqlCode code={measure.plan.join('\n')} />
          {measure.remaining.length ? (
            <p className="flex gap-1.5 text-xs text-amber-800 dark:text-amber-300">
              <CircleX className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {measure.remaining[0]}
            </p>
          ) : (
            <p className="flex gap-1.5 text-xs text-emerald-700 dark:text-emerald-400">
              <CircleCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Rejada taqiqlangan tugun yo'q.
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-destructive">{measure.error}</p>
      )}
    </div>
  )
}

/** Indeks laboratoriyasi: rejaning AI tushuntirishi va (yechilgandan keyin) AI muqobil indeksining o'lchovi. */
export function PlanAssistant({ labId, code, solved }: { labId: number; code: string; solved: boolean }) {
  const explain = useMutation({
    mutationFn: () =>
      api<PlanExplanation>(`/labs/${labId}/explain-plan/`, { method: 'POST', body: { sql_code: code, mode: 'explain' } }),
    onError: (error) => toast.error(errorMessage(error)),
  })
  const suggest = useMutation({
    mutationFn: () =>
      api<PlanSuggestion>(`/labs/${labId}/explain-plan/`, { method: 'POST', body: { sql_code: code, mode: 'suggest' } }),
    onError: (error) => toast.error(errorMessage(error)),
  })
  const busy = explain.isPending || suggest.isPending
  const canRun = !busy && Boolean(code.trim())

  return (
    <div className="grid gap-3 rounded-lg border p-3">
      <div className="flex items-center gap-1.5 text-sm font-medium">
        <Gauge className="size-4" aria-hidden="true" />
        Reja yordamchisi
      </div>
      <p className="text-xs text-muted-foreground">
        AI kodingizdan oldingi va keyingi rejani o'zbekcha tushuntiradi, lekin qaysi indeks kerakligini aytmaydi.
        {solved
          ? " Laboratoriyani yechdingiz: endi AI muqobil indeksini ham ko'rishingiz mumkin, tizim uni haqiqatan yaratib o'lchaydi."
          : ' Laboratoriyani yechganingizdan keyin AI muqobil indeksini taklif qiladi.'}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" disabled={!canRun} onClick={() => explain.mutate()}>
          {explain.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
          Rejani tushuntirish
        </Button>
        {solved ? (
          <Button type="button" variant="outline" disabled={!canRun} onClick={() => suggest.mutate()}>
            {suggest.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Gauge aria-hidden="true" />}
            AI muqobil indeksi
          </Button>
        ) : null}
      </div>

      {explain.data ? (
        <div className="grid gap-3" aria-live="polite">
          <p className="text-sm whitespace-pre-wrap">{explain.data.explanation}</p>
          <div className="grid gap-3 lg:grid-cols-2">
            <MeasureView title="Kodingizsiz" measure={explain.data.before} />
            <MeasureView title="Kodingizdan keyin" measure={explain.data.after} />
          </div>
        </div>
      ) : null}

      {suggest.data ? (
        <div className="grid gap-3 border-t pt-3" aria-live="polite">
          <div className="text-sm font-medium">AI taklifi</div>
          <SqlCode code={suggest.data.index_sql} />
          <p className="text-sm whitespace-pre-wrap">{suggest.data.explanation}</p>
          <div className="grid gap-3 lg:grid-cols-2">
            <MeasureView title="Sizning indeksingiz" measure={suggest.data.mine} />
            <MeasureView title="AI indeksi (tizim o'lchadi)" measure={suggest.data.suggestion} />
          </div>
          <p className="text-xs text-muted-foreground">
            Narx — rejalashtiruvchining shartli baholashi: kichikroq bo'lsa, so'rov tezroq. AI gapiga emas, shu o'lchovga
            ishoning.
          </p>
        </div>
      ) : null}
    </div>
  )
}
