import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, Loader2, Search, Send, Sparkles, Wrench } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { ConfidencePicker } from '@/components/ConfidencePicker'
import { ErEditor, ErFixLegend } from '@/components/ErEditor'
import { AiAdvice, GradeCard } from '@/components/LabRunner'
import { SelfExplain } from '@/components/SelfExplain'
import { Button } from '@/components/ui/button'
import { api, apiFetch, errorMessage, fieldErrors } from '@/lib/api'
import { useConfidence } from '@/lib/confidence'
import { cleanDiagram, EMPTY_DIAGRAM, snapshotDiagram } from '@/lib/er'
import type { ErDiagram, ErFix, LabRunResult } from '@/lib/types'

function ErVerdict({ result }: { result: LabRunResult }) {
  if (result.is_correct) {
    return (
      <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-emerald-900" role="status">
        <div className="flex items-center gap-2 font-medium">
          <CircleCheck className="size-5 shrink-0" aria-hidden="true" />
          To'g'ri!
        </div>
        <p className="mt-1 text-sm">Diagramma namunaviy loyiha bilan to'liq mos keldi.</p>
        {result.ai_explain && result.attempt_id ? (
          <div className="mt-3">
            <SelfExplain attemptId={result.attempt_id} kind="er" />
          </div>
        ) : null}
      </div>
    )
  }
  return (
    <div className="grid gap-3 rounded-lg border border-red-300 bg-red-50 p-3 text-red-900" role="alert">
      <div className="flex items-center gap-2 font-medium">
        <CircleX className="size-5 shrink-0" aria-hidden="true" />
        Diagrammada xatolar bor
      </div>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {result.differences.map((difference, index) => (
          <li key={index}>{difference}</li>
        ))}
      </ul>
      {/* Topshirilganda maslahat o'rniga tuzatilgan loyiha va AI tushuntirishi ko'rsatiladi */}
      {result.ai_available && result.attempt_id && !result.grade ? <AiAdvice attemptId={result.attempt_id} /> : null}
    </div>
  )
}

/** Baholashga topshirilgan noto'g'ri diagrammaning tuzatilgan varianti va AI tushuntirishi */
export function ErFixView({ fix }: { fix: ErFix }) {
  return (
    <div className="grid gap-3 rounded-lg border bg-card p-3">
      <div className="flex items-center gap-2 font-medium">
        <Wrench className="size-5 shrink-0 text-primary" aria-hidden="true" />
        Tuzatilgan loyiha
      </div>
      <p className="text-sm text-muted-foreground">
        Diagrammangiz asosida tuzatilgan variant. Ranglar nima o'zgarganini ko'rsatadi; obyektlarni sudrab joylashtirish
        mumkin. Uni o'rganib, o'z diagrammangizni tuzating va qayta topshiring.
      </p>
      <ErFixLegend />
      <ErEditor value={fix.diagram} className="h-[26rem]" />
      {fix.diagram.changes.length ? (
        <div>
          <h3 className="mb-1 text-sm font-medium">O'zgarishlar</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {fix.diagram.changes.map((change, index) => (
              <li key={index}>{change}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {fix.explanation ? (
        <div className="rounded-lg border bg-background p-3">
          <div className="mb-1 flex items-center gap-1.5 text-sm font-medium">
            <Sparkles className="size-4" aria-hidden="true" />
            AI tushuntirishi: nima uchun shunday
          </div>
          <p className="text-sm whitespace-pre-wrap">{fix.explanation}</p>
        </div>
      ) : null}
    </div>
  )
}

type RunMode = 'run' | 'submit'

interface ErLabRunnerProps {
  labId: number
  initialDiagram?: ErDiagram | null
  /** Oldingi topshirishning tuzatilgan varianti (sahifa qayta ochilganda) */
  initialFix?: ErFix | null
  /** true bo'lsa, "Baholashga topshirish" tugmasi ham ko'rinadi (talaba uchun) */
  gradable?: boolean
  onResult?: (result: LabRunResult, diagram: ErDiagram) => void
  /** Diagramma o'zgarganda (murabbiyga hozirgi ishni yuborish uchun) */
  onDiagramChange?: (diagram: ErDiagram) => void
  /** true bo'lsa, chizish jarayoni yoziladi (talaba uchun; o'qituvchi uni «Jarayon» oynasida ko'radi) */
  record?: boolean
}

const SNAPSHOT_INTERVAL_MS = 10_000

/**
 * Chizish jarayonini yozish: diagramma o'zgargan bo'lsa, har 10 soniyada, sahifa yashirilganda va muharrir
 * yopilganda oraliq holat serverga yuboriladi. Xato talabaga ko'rsatilmaydi: keyingi o'zgarishda qayta yuboriladi.
 */
function useErRecorder(labId: number, diagram: ErDiagram, enabled: boolean) {
  const latest = useRef(diagram)
  const sent = useRef(JSON.stringify(snapshotDiagram(diagram)))

  useEffect(() => {
    latest.current = diagram
  }, [diagram])

  useEffect(() => {
    if (!enabled) return
    function flush(keepalive = false) {
      const snapshot = snapshotDiagram(latest.current)
      const text = JSON.stringify(snapshot)
      if (text === sent.current) return
      sent.current = text
      apiFetch(`/labs/${labId}/er-snapshot/`, { method: 'POST', body: { diagram: snapshot }, keepalive }).catch(
        () => undefined,
      )
    }
    function onVisibilityChange() {
      if (document.visibilityState === 'hidden') flush(true)
    }
    const timer = window.setInterval(flush, SNAPSHOT_INTERVAL_MS)
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      flush(true)
    }
  }, [labId, enabled])
}

/** ER-diagramma muharriri, tekshirish va baholashga topshirish. */
export function ErLabRunner({
  labId,
  initialDiagram,
  initialFix = null,
  gradable = false,
  onResult,
  onDiagramChange,
  record = false,
}: ErLabRunnerProps) {
  const [diagram, setDiagram] = useState<ErDiagram>(initialDiagram ?? EMPTY_DIAGRAM)
  useErRecorder(labId, diagram, record)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const confidence = useConfidence()

  const mutation = useMutation({
    mutationFn: ({ mode, level }: { mode: RunMode; level: number | null }) =>
      api<LabRunResult>(`/labs/${labId}/${mode}/`, {
        method: 'POST',
        body: { diagram: cleanDiagram(diagram), ...confidence.body(level) },
      }),
    onSuccess: (result, { level }) => {
      if (gradable) confidence.record(level, result.is_correct)
      onResult?.(result, diagram)
    },
    onError: (error) => {
      const message = fieldErrors(error).diagram
      if (message) setFieldError(message)
      else toast.error(errorMessage(error))
    },
  })

  function run(mode: RunMode) {
    setFieldError(null)
    mutation.mutate({ mode, level: gradable ? confidence.value : null })
  }

  const canRun = !mutation.isPending && diagram.entities.length > 0
  const submitting = mutation.isPending && mutation.variables?.mode === 'submit'
  const running = mutation.isPending && !submitting
  const result = mutation.data
  // Yangi topshirish natijasi bo'lsa o'sha, aks holda oldingi topshirishning tuzatishi
  const fix = result && 'fix' in result ? result.fix : initialFix

  return (
    <div className="grid gap-4">
      <ErEditor
        value={diagram}
        onChange={(next) => {
          setDiagram(next)
          setFieldError(null)
          onDiagramChange?.(next)
        }}
      />
      {fieldError ? (
        <p className="text-sm text-destructive" role="alert">
          {fieldError}
        </p>
      ) : null}
      {gradable ? <ConfidencePicker value={confidence.value} onChange={confidence.setValue} note={confidence.note} /> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button size="lg" variant={gradable ? 'outline' : 'default'} disabled={!canRun} onClick={() => run('run')}>
          {running ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Search aria-hidden="true" />}
          {running ? 'Tekshirilmoqda…' : 'Tekshirish'}
        </Button>
        {gradable ? (
          <Button size="lg" disabled={!canRun} onClick={() => run('submit')}>
            {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
            {submitting ? 'Baholanmoqda…' : 'Baholashga topshirish'}
          </Button>
        ) : null}
      </div>
      {gradable ? (
        <p className="text-xs text-muted-foreground">
          «Tekshirish» xatolarni ko'rsatadi va AI maslahat beradi, lekin to'g'ri javobni aytmaydi. «Baholashga
          topshirish»dan keyin ball qo'yiladi va diagrammangizning tuzatilgan varianti ko'rsatiladi. Qayta topshirish
          mumkin, eng yuqori ball saqlanadi.
        </p>
      ) : null}

      {result && !mutation.isPending ? (
        <div className="grid gap-4" aria-live="polite">
          {result.grade ? <GradeCard grade={result.grade} best={result.best_grade} /> : null}
          <ErVerdict result={result} />
        </div>
      ) : null}
      {fix && !mutation.isPending ? <ErFixView fix={fix} /> : null}
    </div>
  )
}
