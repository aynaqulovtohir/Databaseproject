import { useMutation, useQuery } from '@tanstack/react-query'
import { Award, CircleCheck, CircleX, Lightbulb, Loader2, Play, Send, Sparkles } from 'lucide-react'
import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage, fieldErrors } from '@/lib/api'
import { GRADE_SOURCE_LABELS, MAX_SCORE, type LabGrade, type LabRunResult, type LabRunTable } from '@/lib/types'

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

/** Xato urinish uchun AI maslahati: natija kelishi bilan o'zi so'raladi. */
function AiAdvice({ attemptId }: { attemptId: number }) {
  const advice = useQuery({
    queryKey: ['lab-advice', attemptId],
    queryFn: () => api<{ advice: string }>(`/labs/attempts/${attemptId}/advice/`, { method: 'POST' }),
    staleTime: Infinity,
    retry: false,
  })

  return (
    <div className="rounded-lg border bg-background p-3">
      <div className="mb-1 flex items-center gap-1.5 text-sm font-medium text-foreground">
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
        <p className="text-sm whitespace-pre-wrap text-foreground">{advice.data.advice}</p>
      )}
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
          {result.checked_against_solution
            ? 'Kod xatosiz ishladi va natija kutilgan natija bilan mos keldi.'
            : 'Kod xatosiz ishladi.'}
        </p>
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
        <div className="grid gap-1 text-sm">
          <p className="font-mono text-xs break-words">
            {error.line ? `${error.line}-qator: ` : ''}
            {error.message}
          </p>
          {error.detail ? <p className="font-mono text-xs break-words">{error.detail}</p> : null}
          {error.hint ? <p className="font-mono text-xs break-words">Hint: {error.hint}</p> : null}
        </div>
      ) : (
        <p className="text-sm">Kod xatosiz ishladi, lekin natija kutilganidan farq qiladi:</p>
      )}
      {result.differences.length ? (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {result.differences.map((difference, index) => (
            <li key={index}>{difference}</li>
          ))}
        </ul>
      ) : null}
      {error?.tip ? (
        <div className="flex gap-2 rounded-lg border bg-background p-3 text-sm text-foreground">
          <Lightbulb className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            <span className="font-medium">Maslahat: </span>
            {error.tip}
          </p>
        </div>
      ) : null}
      {result.ai_available && result.attempt_id ? <AiAdvice attemptId={result.attempt_id} /> : null}
    </div>
  )
}

function GradeCard({ grade, best }: { grade: LabGrade; best?: LabGrade }) {
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
}

/** SQL muharriri, "Ishga tushirish" tugmasi va natija paneli. */
export function LabRunner({ labId, initialCode = '', gradable = false, onResult }: LabRunnerProps) {
  const [code, setCode] = useState(initialCode)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: ({ sqlCode, mode }: { sqlCode: string; mode: RunMode }) =>
      api<LabRunResult>(`/labs/${labId}/${mode}/`, { method: 'POST', body: { sql_code: sqlCode } }),
    onSuccess: (result, { sqlCode }) => onResult?.(result, sqlCode),
    onError: (error) => {
      const message = fieldErrors(error).sql_code
      if (message) setFieldError(message)
      else toast.error(errorMessage(error))
    },
  })

  const canRun = !mutation.isPending && Boolean(code.trim())

  function run(mode: RunMode = 'run') {
    if (!canRun) return
    setFieldError(null)
    mutation.mutate({ sqlCode: code, mode })
  }

  const submitting = mutation.isPending && mutation.variables?.mode === 'submit'
  const running = mutation.isPending && !submitting

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    run()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      run()
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
            onChange={(event) => setCode(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          {fieldError ? (
            <p className="text-xs text-destructive" role="alert">
              {fieldError}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" size="lg" variant={gradable ? 'outline' : 'default'} disabled={!canRun}>
            {running ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
            {running ? 'Bajarilmoqda…' : 'Ishga tushirish'}
          </Button>
          {gradable ? (
            <Button type="button" size="lg" disabled={!canRun} onClick={() => run('submit')}>
              {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
              {submitting ? 'Baholanmoqda…' : 'Baholashga topshirish'}
            </Button>
          ) : null}
          <span className="text-xs text-muted-foreground">Ctrl + Enter — ishga tushirish</span>
        </div>
        {gradable ? (
          <p className="text-xs text-muted-foreground">
            Avval «Ishga tushirish» bilan sinab ko'ring. Tayyor bo'lgach «Baholashga topshirish»ni bosing: kodingizga
            ball qo'yiladi. Qayta topshirish mumkin, eng yuqori ball saqlanadi.
          </p>
        ) : null}
      </form>

      {result && !mutation.isPending ? (
        <div className="grid gap-4" aria-live="polite">
          {result.grade ? <GradeCard grade={result.grade} best={result.best_grade} /> : null}
          <Verdict result={result} />
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
