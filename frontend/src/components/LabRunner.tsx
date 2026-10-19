import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Award, CircleCheck, CircleX, FlaskConical, Lightbulb, Loader2, Play, Send, Sparkles } from 'lucide-react'
import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { toast } from 'sonner'

import { ConfidencePicker } from '@/components/ConfidencePicker'
import { PlanAssistant } from '@/components/PlanAssistant'
import { ProbeResults } from '@/components/Probes'
import { SelfExplain } from '@/components/SelfExplain'
import { SqlCode } from '@/components/SqlCode'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage, fieldErrors } from '@/lib/api'
import { useConfidence } from '@/lib/confidence'
import {
  GRADE_SOURCE_LABELS,
  MAX_SCORE,
  type LabGrade,
  type LabRunError,
  type LabRunResult,
  type LabConcurrentStep,
  type LabRunTable,
  type LabTryResult,
  type LabTryTable,
} from '@/lib/types'
import { cn } from '@/lib/utils'

const MAX_SQL_LENGTH = 50_000

function ResultTable({ table }: { table: LabRunTable }) {
  if (!table.columns.length) return null
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium">
        So'rov natijasi <span className="font-normal text-muted-foreground">({table.row_count} qator)</span>
      </h3>
      <div className="max-h-80 overflow-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              {table.columns.map((column, index) => (
                <TableHead key={index} className="font-mono text-xs">
                  {column}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {table.rows.map((row, rowIndex) => (
              <TableRow key={rowIndex}>
                {row.map((value, columnIndex) => (
                  <TableCell key={columnIndex} className="font-mono text-xs whitespace-pre-wrap">
                    {value === null ? <span className="text-muted-foreground italic">NULL</span> : value}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {!table.rows.length ? <p className="mt-2 text-xs text-muted-foreground">So'rov hech qanday qator qaytarmadi.</p> : null}
      {table.truncated ? (
        <p className="mt-2 text-xs text-muted-foreground">Faqat dastlabki {table.rows.length} qator ko'rsatildi.</p>
      ) : null}
    </div>
  )
}

interface AdviceResponse {
  advice: string
  hints: string[]
  level: number
  max_level: number
}

const HINT_TITLES = ['Yo\'naltiruvchi savol', 'Tushuncha', 'Aniq ko\'rsatma']

/** Bosqichma-bosqich AI maslahati: 1-daraja o'zi so'raladi, keyingisini talaba tugma bilan oladi. */
export function AiAdvice({ attemptId }: { attemptId: number }) {
  const queryClient = useQueryClient()
  const key = ['lab-advice', attemptId]
  const advice = useQuery({
    queryKey: key,
    queryFn: () => api<AdviceResponse>(`/labs/attempts/${attemptId}/advice/`, { method: 'POST' }),
    staleTime: Infinity,
    retry: false,
  })
  const more = useMutation({
    mutationFn: (level: number) =>
      api<AdviceResponse>(`/labs/attempts/${attemptId}/advice/`, { method: 'POST', body: { level } }),
    onSuccess: (data) => queryClient.setQueryData(key, data),
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <div className="grid gap-2 rounded-lg border bg-background p-3">
      <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
        <Sparkles className="size-4" aria-hidden="true" />
        AI maslahati
      </div>
      {advice.isPending ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Maslahat tayyorlanmoqda…
        </p>
      ) : advice.isError ? (
        <p className="text-sm text-muted-foreground">{errorMessage(advice.error)}</p>
      ) : (
        <>
          {advice.data.hints.map((hint, index) => (
            <div key={index} className="text-sm text-foreground">
              <span className="text-xs font-medium text-muted-foreground">
                {index + 1}-daraja: {HINT_TITLES[index] ?? ''}
              </span>
              <p className="whitespace-pre-wrap">{hint}</p>
            </div>
          ))}
          {advice.data.level < advice.data.max_level ? (
            <Button
              type="button"
              variant="outline"
              className="justify-self-start"
              disabled={more.isPending}
              onClick={() => more.mutate(advice.data.level + 1)}
            >
              {more.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Lightbulb aria-hidden="true" />}
              Ko'proq yordam ({advice.data.level + 1}/{advice.data.max_level})
            </Button>
          ) : null}
        </>
      )}
    </div>
  )
}

const STEP_STATUS: Record<LabConcurrentStep['status'], { label: string; className: string }> = {
  ok: { label: 'bajarildi', className: 'text-muted-foreground' },
  waiting: { label: 'qulf kutmoqda…', className: 'text-amber-700 dark:text-amber-400' },
  resumed: { label: 'kutgandan keyin bajarildi', className: 'text-amber-700 dark:text-amber-400' },
  error: { label: 'xato', className: 'text-destructive' },
}

/** Ikki sessiya (A va B) buyruqlari qanday ketma-ketlikda bajarilgani va har biri nimani o'qigani. */
function ConcurrencyTimeline({ steps }: { steps?: LabConcurrentStep[] }) {
  if (!steps?.length) return null
  return (
    <div>
      <h3 className="mb-1 text-sm font-medium">Vaqt chizig'i: ikki sessiya bir vaqtda</h3>
      <p className="mb-2 text-xs text-muted-foreground">
        Yuqoridan pastga — vaqt tartibida. A va B — kodingizni bir vaqtda bajargan ikki sessiya.
      </p>
      <ol className="grid gap-1.5">
        {steps.map((step, index) => {
          const status = STEP_STATUS[step.status]
          return (
            <li
              key={index}
              className={cn(
                'grid min-w-0 gap-1 rounded-lg border p-2 text-xs sm:w-[85%]',
                step.session === 'B' ? 'sm:justify-self-end bg-muted/40' : 'sm:justify-self-start',
              )}
            >
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-semibold">{step.session}</span>
                <span className="min-w-0 font-mono break-all">{step.sql}</span>
              </div>
              <div className={status.className}>
                {status.label}
                {step.message ? `: ${step.message}` : ''}
              </div>
              {step.rows.length ? (
                <div className="font-mono text-muted-foreground">
                  o'qidi: {step.columns.join(', ')} = {step.rows.map((row) => row.join(', ')).join('; ')}
                </div>
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function PlanView({ plan }: { plan?: string[] | null }) {
  if (!plan?.length) return null
  return (
    <div>
      <h3 className="mb-1 text-sm font-medium">So'rov rejasi (EXPLAIN)</h3>
      <p className="mb-2 text-xs text-muted-foreground">
        Shartdagi so'rov qanday bajarilishi: Seq Scan — jadval to'liq o'qiladi, Index Scan — indeks ishlatiladi.
      </p>
      <SqlCode code={plan.join('\n')} />
    </div>
  )
}

function ErrorDetails({ error }: { error: LabRunError }) {
  return (
    <div className="grid gap-1 text-sm">
      <p className="font-mono text-xs break-words">
        {error.line ? `${error.line}-qator: ` : ''}
        {error.message}
      </p>
      {error.detail ? <p className="font-mono text-xs break-words">{error.detail}</p> : null}
      {error.hint ? <p className="font-mono text-xs break-words">Hint: {error.hint}</p> : null}
    </div>
  )
}

function ErrorTip({ tip }: { tip: string }) {
  return (
    <div className="flex gap-2 rounded-lg border bg-background p-3 text-sm text-foreground">
      <Lightbulb className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>
        <span className="font-medium">Maslahat: </span>
        {tip}
      </p>
    </div>
  )
}

function Verdict({ result }: { result: LabRunResult }) {
  if (result.is_correct) {
    return (
      <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-emerald-900" role="status">
        <div className="flex items-center gap-2 font-medium">
          <CircleCheck className="size-5 shrink-0" aria-hidden="true" />
          To'g'ri!
        </div>
        <p className="mt-1 text-sm">
          {result.probes
            ? "Cheklovlar barcha hujumlarni to'xtatdi va to'g'ri ma'lumotni qabul qildi."
            : result.checked_against_solution
              ? 'Kod xatosiz ishladi va natija kutilgan natija bilan mos keldi.'
              : 'Kod xatosiz ishladi.'}
        </p>
        {result.ai_explain && result.attempt_id ? (
          <div className="mt-3">
            <SelfExplain attemptId={result.attempt_id} kind="sql" />
          </div>
        ) : null}
      </div>
    )
  }

  const { error } = result
  return (
    <div className="grid gap-3 rounded-lg border border-red-300 bg-red-50 p-3 text-red-900" role="alert">
      <div className="flex items-center gap-2 font-medium">
        <CircleX className="size-5 shrink-0" aria-hidden="true" />
        {error ? 'Kod xato berdi' : "Natija noto'g'ri"}
      </div>
      {error ? (
        <ErrorDetails error={error} />
      ) : (
        <p className="text-sm">
          {result.probes
            ? "Kod xatosiz ishladi, lekin ba'zi sinovlar o'tmadi:"
            : 'Kod xatosiz ishladi, lekin natija kutilganidan farq qiladi:'}
        </p>
      )}
      {result.differences.length ? (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {result.differences.map((difference, index) => (
            <li key={index}>{difference}</li>
          ))}
        </ul>
      ) : null}
      {error?.tip ? <ErrorTip tip={error.tip} /> : null}
      {result.ai_available && result.attempt_id ? <AiAdvice attemptId={result.attempt_id} /> : null}
    </div>
  )
}

function TablesSummary({ tables }: { tables: LabTryTable[] }) {
  if (!tables.length) return null
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium">Bazadagi jadvallar</h3>
      <div className="grid gap-2 sm:grid-cols-2">
        {tables.map((table) => (
          <div key={table.name} className="min-w-0 rounded-lg border p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-2">
              <span className="font-mono text-sm font-medium break-all">{table.name}</span>
              <span className="text-xs text-muted-foreground">
                {table.row_count}
                {table.rows_truncated ? '+' : ''} qator
              </span>
            </div>
            <ul className="mt-2 grid gap-0.5 font-mono text-xs">
              {table.columns.map((column) => (
                <li key={column.name} className="break-all">
                  {column.name} <span className="text-muted-foreground">{column.type}</span>
                  {column.not_null ? <span className="text-muted-foreground"> NOT NULL</span> : null}
                </li>
              ))}
            </ul>
            {table.constraints.length ? (
              <ul className="mt-2 grid gap-0.5 border-t pt-2 font-mono text-xs text-muted-foreground">
                {table.constraints.map((constraint, index) => (
                  <li key={index} className="break-all">
                    {constraint}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

/** Erkin sinash natijasi: to'g'ri/noto'g'ri deb baholanmaydi */
function TryResult({ result }: { result: LabTryResult }) {
  const { error } = result
  return (
    <div className="grid gap-4">
      {error ? (
        <div className="grid gap-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-950" role="alert">
          <div className="flex items-center gap-2 font-medium">
            <CircleX className="size-5 shrink-0" aria-hidden="true" />
            Kod xato berdi
          </div>
          <ErrorDetails error={error} />
          {error.tip ? <ErrorTip tip={error.tip} /> : null}
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/40 p-3 text-sm" role="status">
          <div className="flex items-center gap-2 font-medium">
            <FlaskConical className="size-4 shrink-0" aria-hidden="true" />
            Kod xatosiz bajarildi
            {result.status_message ? (
              <span className="font-mono text-xs font-normal text-muted-foreground">({result.status_message})</span>
            ) : null}
          </div>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Bu sinov: natija namunaviy yechim bilan solishtirilmadi va urinish hisoblanmadi.
      </p>
      <PlanView plan={result.plan} />
      <ConcurrencyTimeline steps={result.steps} />
      {result.result ? <ResultTable table={result.result} /> : null}
      <TablesSummary tables={result.tables} />
    </div>
  )
}

export function GradeCard({ grade, best }: { grade: LabGrade; best?: LabGrade }) {
  return (
    <div className="rounded-lg border bg-card p-3" role="status">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Award className="size-5 shrink-0 text-primary" aria-hidden="true" />
        <span className="text-lg font-semibold tabular-nums">
          {grade.score} / {MAX_SCORE}
        </span>
        <span className="text-xs text-muted-foreground">{GRADE_SOURCE_LABELS[grade.source]}</span>
      </div>
      {grade.comment ? <p className="mt-2 text-sm whitespace-pre-wrap">{grade.comment}</p> : null}
      {best && best.score > grade.score ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Bahoyingiz o'zgarmadi: oldingi eng yuqori ballingiz {best.score} saqlanib qoldi.
        </p>
      ) : null}
    </div>
  )
}

type RunMode = 'run' | 'submit'

interface LabRunnerProps {
  labId: number
  initialCode?: string
  /** true bo'lsa, "Baholashga topshirish" tugmasi ham ko'rinadi (talaba uchun) */
  gradable?: boolean
  /** Har bir ishga tushirish yoki topshirishdan keyin chaqiriladi */
  onResult?: (result: LabRunResult, code: string) => void
  /** Indeks laboratoriyasida: AI reja yordamchisi ko'rsatiladi (AI yoqilgan bo'lsa) */
  planAssistant?: boolean
  /** Laboratoriya yechilganmi: AI muqobil indeksi faqat shundan keyin ochiladi */
  solved?: boolean
  /** Muharrirdagi kod o'zgarganda (murabbiyga hozirgi ishni yuborish uchun) */
  onCodeChange?: (code: string) => void
}

/** SQL muharriri, «Sinab ko'rish» va «Tekshirish» tugmalari va natija paneli. */
export function LabRunner({
  labId,
  initialCode = '',
  gradable = false,
  onResult,
  planAssistant = false,
  solved = false,
  onCodeChange,
}: LabRunnerProps) {
  const [code, setCode] = useState(initialCode)
  const [fieldError, setFieldError] = useState<string | null>(null)
  // Talaba tekshirishdan oldin o'z javobiga ishonchini belgilaydi (kalibrlash uchun, ixtiyoriy)
  const confidence = useConfidence()

  const mutation = useMutation({
    mutationFn: ({ sqlCode, mode, level }: { sqlCode: string; mode: RunMode; level: number | null }) =>
      api<LabRunResult>(`/labs/${labId}/${mode}/`, { method: 'POST', body: { sql_code: sqlCode, ...confidence.body(level) } }),
    onSuccess: (result, { sqlCode, level }) => {
      if (gradable) confidence.record(level, result.is_correct)
      onResult?.(result, sqlCode)
    },
    onError: (error) => {
      const message = fieldErrors(error).sql_code
      if (message) setFieldError(message)
      else toast.error(errorMessage(error))
    },
  })

  // Erkin sinash: alohida so'rov, natijasi tekshiruv natijasi o'rnida ko'rsatiladi
  const tryMutation = useMutation({
    mutationFn: (sqlCode: string) =>
      api<LabTryResult>(`/labs/${labId}/try/`, { method: 'POST', body: { sql_code: sqlCode } }),
    onError: (error) => {
      const message = fieldErrors(error).sql_code
      if (message) setFieldError(message)
      else toast.error(errorMessage(error))
    },
  })
  const [shown, setShown] = useState<'check' | 'try'>('check')

  const busy = mutation.isPending || tryMutation.isPending
  const canRun = !busy && Boolean(code.trim())

  function run(mode: RunMode = 'run') {
    if (!canRun) return
    setFieldError(null)
    setShown('check')
    mutation.mutate({ sqlCode: code, mode, level: gradable ? confidence.value : null })
  }

  function tryCode() {
    if (!canRun) return
    setFieldError(null)
    setShown('try')
    tryMutation.mutate(code)
  }

  const submitting = mutation.isPending && mutation.variables?.mode === 'submit'
  const running = mutation.isPending && !submitting
  const trying = tryMutation.isPending

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    run()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      if (event.shiftKey) tryCode()
      else run()
    }
  }

  const result = mutation.data

  return (
    <div className="grid gap-4">
      <form onSubmit={handleSubmit} className="grid gap-3" noValidate>
        <div className="grid gap-1.5">
          <label htmlFor="lab_code" className="text-sm font-medium">
            SQL kod
          </label>
          <Textarea
            id="lab_code"
            className="max-h-[32rem] min-h-56 font-mono text-sm md:text-xs"
            placeholder="SELECT ..."
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            maxLength={MAX_SQL_LENGTH}
            aria-invalid={Boolean(fieldError)}
            value={code}
            onChange={(event) => {
              setCode(event.target.value)
              onCodeChange?.(event.target.value)
            }}
            onKeyDown={handleKeyDown}
          />
          {fieldError ? (
            <p className="text-xs text-destructive" role="alert">
              {fieldError}
            </p>
          ) : null}
        </div>
        {gradable ? <ConfidencePicker value={confidence.value} onChange={confidence.setValue} note={confidence.note} /> : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" size="lg" variant="outline" disabled={!canRun} onClick={tryCode}>
            {trying ? <Loader2 className="animate-spin" aria-hidden="true" /> : <FlaskConical aria-hidden="true" />}
            {trying ? 'Bajarilmoqda…' : "Sinab ko'rish"}
          </Button>
          <Button type="submit" size="lg" variant={gradable ? 'outline' : 'default'} disabled={!canRun}>
            {running ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
            {running ? 'Tekshirilmoqda…' : 'Tekshirish'}
          </Button>
          {gradable ? (
            <Button type="button" size="lg" disabled={!canRun} onClick={() => run('submit')}>
              {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
              {submitting ? 'Baholanmoqda…' : 'Baholashga topshirish'}
            </Button>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">
          «Sinab ko'rish» kodni bajarib natijasini ko'rsatadi, lekin tekshirmaydi va urinish hisoblanmaydi
          (Ctrl + Shift + Enter). «Tekshirish» natijani kutilgan natija bilan solishtiradi (Ctrl + Enter).
          {gradable
            ? " Tayyor bo'lgach «Baholashga topshirish»ni bosing: kodingizga ball qo'yiladi. Qayta topshirish mumkin, eng yuqori ball saqlanadi."
            : ''}
        </p>
      </form>

      {planAssistant ? <PlanAssistant labId={labId} code={code} solved={solved} /> : null}

      {shown === 'try' && tryMutation.data && !busy ? (
        <div aria-live="polite">
          <TryResult result={tryMutation.data} />
        </div>
      ) : null}

      {shown === 'check' && result && !busy ? (
        <div className="grid gap-4" aria-live="polite">
          {result.grade ? <GradeCard grade={result.grade} best={result.best_grade} /> : null}
          <Verdict result={result} />
          <ProbeResults result={result} />
          <PlanView plan={result.plan} />
          <ConcurrencyTimeline steps={result.steps} />
          {result.result ? <ResultTable table={result.result} /> : null}
          {!result.error && !result.result && result.status_message ? (
            <p className="text-xs text-muted-foreground">
              Oxirgi buyruq: <span className="font-mono">{result.status_message}</span>
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
