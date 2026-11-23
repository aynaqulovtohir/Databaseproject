import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Info } from 'lucide-react'

import { ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { Quiz, QuizAnalysis, QuizQuestionAnalysis, ScaleLabel, SurveyScaleAnalysis } from '@/lib/types'
import { cn } from '@/lib/utils'
import { t } from '@/lib/i18n'

function format(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

function percent(value: number | null) {
  return value === null ? '—' : `${Math.round(100 * value)}%`
}

const VERDICT_VARIANT = { good: 'secondary', review: 'outline', replace: 'destructive' } as const

function AlphaTile({ name, alpha, interpretation, hint }: { name: string; alpha: number | null; interpretation: ScaleLabel | null; hint: string }) {
  return (
    <div className="rounded-xl border bg-card p-3">
      <div className="text-sm text-muted-foreground">{t('Ishonchlilik ({name})', { name })}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums">{format(alpha, 3)}</span>
        {interpretation ? <Badge variant="outline">{interpretation.label}</Badge> : null}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
    </div>
  )
}

/** Variantlar tahlili: har bir variantni tanlaganlar ulushi — hammasi, kuchli (yuqori 27%) va kuchsiz (quyi 27%) */
function Choices({ question, groups }: { question: QuizQuestionAnalysis; groups: boolean }) {
  return (
    <details className="group mt-1">
      <summary className="flex cursor-pointer list-none items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden="true" />
        {t('Variantlar')}
      </summary>
      <table className="mt-2 w-full text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="py-1 text-left font-normal">{t('Variant')}</th>
            <th className="py-1 text-right font-normal">{t('Hammasi')}</th>
            {groups ? (
              <>
                <th className="py-1 text-right font-normal">{t('Kuchli')}</th>
                <th className="py-1 text-right font-normal">{t('Kuchsiz')}</th>
              </>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {question.choices.map((choice) => (
            <tr key={choice.id} className="border-t align-top">
              <td className="py-1 pr-2">
                <span className={cn(choice.is_correct && 'font-medium')}>
                  {choice.is_correct ? '✓ ' : ''}
                  {choice.text}
                </span>
                {choice.flag ? <span className="block text-amber-700">{choice.flag}</span> : null}
              </td>
              <td className="py-1 text-right tabular-nums">{percent(choice.share)}</td>
              {groups ? (
                <>
                  <td className="py-1 text-right tabular-nums">{percent(choice.upper)}</td>
                  <td className="py-1 text-right tabular-nums">{percent(choice.lower)}</td>
                </>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

function TestView({ data }: { data: Extract<QuizAnalysis, { kind: 'test' }> }) {
  const reliability = data.reliability!
  const groups = Boolean(data.extreme_groups)
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <AlphaTile
          name={reliability.coefficient}
          alpha={reliability.alpha}
          interpretation={reliability.interpretation}
          hint={t('{questions} ta savol, {students} ta talaba. 0.70 dan yuqori — maqbul.', { questions: reliability.questions, students: data.students })}
        />
        <div className="rounded-xl border bg-card p-3">
          <div className="text-sm text-muted-foreground">{t('Umumiy ball')}</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">
            {format(reliability.mean, 1)} <span className="text-base font-normal text-muted-foreground">/ {reliability.max}</span>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {t("SD {sd} · o'lchov xatosi (SEM) {sem}", { sd: format(reliability.sd), sem: format(reliability.sem) })}
          </div>
        </div>
      </div>
      {data.students < data.reliable_students ? (
        <p className="text-xs text-muted-foreground">
          {t("{reliable_students} tadan kam talaba: ko'rsatkichlar dastlabki, savollarni faqat ular asosida almashtirmang.", { reliable_students: data.reliable_students })}
        </p>
      ) : null}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('Savol')}</TableHead>
            <TableHead className="text-right" title={t("O'rtacha ball ulushi: qancha katta bo'lsa, shuncha oson")}>
              {t('Qiyinlik p')}
            </TableHead>
            <TableHead className="text-right" title={t("Savol bali va qolgan savollar yig'indisi korrelyatsiyasi")}>
              {t('Ajratish r')}
            </TableHead>
            <TableHead className="text-right" title={t('Kuchli va kuchsiz 27% talabalar farqi')}>
              {t('D')}
            </TableHead>
            <TableHead className="text-right">{t('α olib tashlansa')}</TableHead>
            <TableHead>{t('Xulosa')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.questions.map((question) => (
            <TableRow key={question.id} className="align-top">
              <TableCell className="max-w-md whitespace-normal">
                <div className="text-sm">
                  {question.order}. {question.text}
                </div>
                {question.advice.length ? (
                  <ul className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
                    {question.advice.map((text) => (
                      <li key={text}>{text}</li>
                    ))}
                  </ul>
                ) : null}
                <Choices question={question} groups={groups} />
              </TableCell>
              <TableCell className="text-right tabular-nums">{format(question.p)}</TableCell>
              <TableCell className="text-right tabular-nums">
                {format(question.r)}
                {question.discrimination ? <span className="block text-xs text-muted-foreground">{question.discrimination.label}</span> : null}
              </TableCell>
              <TableCell className="text-right tabular-nums">{format(question.d)}</TableCell>
              <TableCell className="text-right tabular-nums">{format(question.alpha_if_deleted, 3)}</TableCell>
              <TableCell>
                <Badge variant={VERDICT_VARIANT[question.verdict.key]}>{question.verdict.label}</Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function ScaleView({ scale }: { scale: SurveyScaleAnalysis }) {
  return (
    <div className="grid gap-3">
      <AlphaTile
        name={`Cronbach α · ${scale.label}`}
        alpha={scale.alpha}
        interpretation={scale.interpretation}
        hint={t('{length} ta fikr, hammasiga javob bergan {students} ta talaba', { length: scale.items.length, students: scale.students })}
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('Fikr')}</TableHead>
            <TableHead className="text-right">{t("O'rtacha (1-5)")}</TableHead>
            <TableHead className="text-right">{t("Bog'liqlik r")}</TableHead>
            <TableHead className="text-right">{t('α olib tashlansa')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {scale.items.map((item) => (
            <TableRow key={item.id} className="align-top">
              <TableCell className="max-w-md whitespace-normal">
                <div className="text-sm">
                  {item.order}. {item.text}
                </div>
                {item.advice.map((text) => (
                  <div key={text} className="mt-0.5 text-xs text-muted-foreground">
                    {text}
                  </div>
                ))}
              </TableCell>
              <TableCell className="text-right tabular-nums">{format(item.mean)}</TableCell>
              <TableCell className="text-right tabular-nums">{format(item.r)}</TableCell>
              <TableCell className="text-right tabular-nums">{format(item.alpha_if_deleted, 3)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

/** Test yoki so'rovnomaning psixometrik tahlili (admin va o'qituvchi) */
export function QuizAnalysisCard({ quiz }: { quiz: Quiz }) {
  const survey = quiz.kind === 'survey'
  const analysis = useQuery({
    queryKey: ['quiz-analysis', quiz.id],
    queryFn: () => api<QuizAnalysis>(`/quizzes/${quiz.id}/analysis/`),
  })

  let content
  if (analysis.isPending) content = <ListSkeleton rows={2} />
  else if (analysis.isError) content = <ErrorState error={analysis.error} onRetry={() => void analysis.refetch()} />
  else {
    const data = analysis.data
    content = (
      <div className="grid gap-4">
        {data.consent_required ? (
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              {t("Tadqiqotga rozi bo'lgan {students} ta talabaning javoblari tahlil qilindi", { students: data.students })}
              {data.excluded_no_consent ? t(" ({excluded_no_consent} tasi kirmadi: rozilik yo'q)", { excluded_no_consent: data.excluded_no_consent }) : ''}.
            </span>
          </p>
        ) : null}
        {!data.enough ? (
          <p className="text-sm text-muted-foreground">
            {t("Tahlil uchun kamida {min_students} ta talaba topshirgan va kamida 2 ta savol bo'lishi kerak.", { min_students: data.min_students })}
          </p>
        ) : data.kind === 'test' ? (
          <TestView data={data} />
        ) : (
          data.scales.map((scale) => <ScaleView key={scale.label} scale={scale} />)
        )}
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{survey ? t("So'rovnoma ishonchliligi") : t('Test sifati (psixometrik tahlil)')}</CardTitle>
        <CardDescription>
          {survey
            ? t("Cronbach α — fikrlar bitta narsani izchil o'lchayotganini ko'rsatadi (0.70 dan yuqori — maqbul). Qolgan fikrlar bilan bog'liqligi past fikr boshqa narsani o'lchayotgan yoki teskari ifodalangan bo'lishi mumkin.")
            : t("Dissertatsiyada test ishonchliligi va savollar sifati sifatida keltiriladi. p — qiyinlik (0.20-0.90 oralig'i yaxshi), r — ajratish (0.30 dan yuqori yaxshi, manfiy — kalitni tekshiring). Natija tadqiqot eksportida ham bor (testlar_tahlili.csv).")}
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
