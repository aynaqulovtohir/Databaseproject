import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, CircleX, EyeOff, Loader2, Send } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { ErEditor } from '@/components/ErEditor'
import { PageHeader } from '@/components/PageHeader'
import { SqlCode } from '@/components/SqlCode'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import {
  GRADE_SOURCE_LABELS,
  type Agreement,
  type AgreementStats,
  type BlindReviewItem,
  type BlindReviewQueue,
  type Lab,
} from '@/lib/types'
import { t } from '@/lib/i18n'

function labQuery(labId: string) {
  return labId ? `?lab=${encodeURIComponent(labId)}` : ''
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

function formatShare(value: number | undefined) {
  return value === undefined ? '—' : `${Math.round(value * 100)}%`
}

/** Kohen kappasining odatiy talqini (Landis va Koch) */
function kappaLabel(value: number | null | undefined) {
  if (value === null || value === undefined) return ''
  if (value < 0.2) return t('juda past moslik')
  if (value < 0.4) return t('past moslik')
  if (value < 0.6) return t("o'rtacha moslik")
  if (value < 0.8) return t('yuqori moslik')
  return t('juda yuqori moslik')
}

// ---------- Baholash ----------

function ReviewForm({ item, onSaved }: { item: BlindReviewItem; onSaved: () => void }) {
  const [score, setScore] = useState('')
  const value = Number(score)
  const valid = score.trim() !== '' && Number.isInteger(value) && value >= 0 && value <= 100

  const save = useMutation({
    mutationFn: () => api('/labs/blind-review/', { method: 'POST', body: { attempt: item.attempt_id, score: value } }),
    onSuccess: () => {
      toast.success(t('Baho saqlandi'))
      onSaved()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (valid && !save.isPending) save.mutate()
  }

  const { lab } = item
  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>{lab.title}</CardTitle>
          <CardDescription className="whitespace-pre-wrap">{lab.description}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="grid min-w-0 content-start gap-2">
            <h3 className="text-sm font-medium">{t('Talaba ishi')}</h3>
            {item.diagram ? <ErEditor value={item.diagram} /> : <SqlCode code={item.code || t("(bo'sh)")} />}
            {item.justification ? (
              <div className="grid gap-1 rounded-md border p-2">
                <span className="text-xs font-medium text-muted-foreground">{t('Talabaning yozma asoslashi')}</span>
                <p className="text-sm whitespace-pre-wrap">{item.justification}</p>
              </div>
            ) : null}
            <p className="flex items-center gap-1.5 text-sm">
              {item.is_correct ? (
                <>
                  <CircleCheck className="size-4 text-emerald-600" aria-hidden="true" />
                  {t('Avtomatik tekshiruv: namunaga mos')}
                </>
              ) : (
                <>
                  <CircleX className="size-4 text-destructive" aria-hidden="true" />
                  {t('Avtomatik tekshiruv: namunadan farq qiladi')}
                </>
              )}
            </p>
            {item.check.error ? (
              <p className="rounded-md bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">{item.check.error.message}</p>
            ) : null}
            {item.check.differences.length ? (
              <ul className="list-disc pl-5 text-sm text-muted-foreground">
                {item.check.differences.map((difference) => (
                  <li key={difference}>{difference}</li>
                ))}
              </ul>
            ) : null}
          </div>
          <div className="grid min-w-0 content-start gap-2">
            <h3 className="text-sm font-medium">{t('Namunaviy yechim')}</h3>
            {lab.kind === 'er' && lab.reference_diagram ? (
              <ErEditor value={lab.reference_diagram} />
            ) : (
              <SqlCode code={(lab.solution_sql ?? '').trim()} />
            )}
            {lab.kind === 'sql' && lab.setup_sql ? (
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">{t('Tayyor jadvallar')}</summary>
                <SqlCode code={lab.setup_sql.trim()} />
              </details>
            ) : null}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
            <label className="grid gap-1 text-sm">
              <span className="font-medium">{t('Sizning bahoyingiz (0–100)')}</span>
              <Input
                type="number"
                inputMode="numeric"
                min={0}
                max={100}
                step={1}
                className="h-10 w-32"
                value={score}
                autoFocus
                onChange={(event) => setScore(event.target.value)}
              />
            </label>
            <Button type="submit" size="lg" disabled={!valid || save.isPending}>
              {save.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
              {t('Saqlash va keyingisi')}
            </Button>
            <p className="basis-full text-xs text-muted-foreground">
              {t("Baho bir marta qo'yiladi va keyin o'zgartirilmaydi. Xolis natija uchun bu ishni laboratoriya sahifasida (talaba ismi va tizim bahosi bilan) ochmang.")}
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

function ReviewQueue({ labId }: { labId: string }) {
  const queryClient = useQueryClient()
  const queue = useQuery({
    queryKey: ['blind-review', labId],
    queryFn: () => api<BlindReviewQueue>(`/labs/blind-review/${labQuery(labId)}`),
  })

  if (queue.isPending) return <ListSkeleton rows={2} />
  if (queue.isError) return <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />
  const { item, remaining, reviewed } = queue.data
  return (
    <section className="grid gap-3" aria-label={t('Baholash navbati')}>
      <p className="text-sm text-muted-foreground">
        {t('Baholangan:')}{' '}<span className="font-medium text-foreground tabular-nums">{reviewed}</span>{' '}{t('· Navbatda:')}{' '}
        <span className="font-medium text-foreground tabular-nums">{remaining}</span>
      </p>
      {item ? (
        <ReviewForm
          key={item.attempt_id}
          item={item}
          onSaved={() => {
            void queryClient.invalidateQueries({ queryKey: ['blind-review'] })
            window.scrollTo({ top: 0 })
          }}
        />
      ) : (
        <EmptyState
          icon={EyeOff}
          title={reviewed ? t('Hamma ishlar baholandi') : t("Baholanadigan ish yo'q")}
          description={reviewed ? t("Quyida tizim va sizning baholaringiz mosligini ko'ring.") : t("Talabalar laboratoriyani baholashga topshirgach, ishlar shu yerda paydo bo'ladi.")}
        />
      )}
    </section>
  )
}

// ---------- Moslik ----------

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md bg-card p-5 shadow-(--card-shadow) dark:ring-1 dark:ring-foreground/10">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 font-heading text-2xl font-bold text-heading tabular-nums">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  )
}

const PLOT = { size: 320, pad: 40 }
/** Bundan kam juftlikda korrelyatsiya va kappa tasodifga juda bog'liq */
const MIN_RELIABLE_PAIRS = 30

/** Tarqalish diagrammasi: x — o'qituvchi, y — tizim bahosi. Diagonaldan yuqorisi — tizim yumshoqroq. */
function ScatterPlot({ pairs }: { pairs: Agreement['pairs'] }) {
  const [hover, setHover] = useState<number | null>(null)
  const inner = PLOT.size - PLOT.pad - 12
  const x = (value: number) => PLOT.pad + (value / 100) * inner
  const y = (value: number) => 12 + inner - (value / 100) * inner
  const ticks = [0, 25, 50, 75, 100]
  const active = hover === null ? null : pairs[hover]

  return (
    <figure className="grid gap-2">
      <div className="relative mx-auto w-full max-w-sm">
        <svg viewBox={`0 0 ${PLOT.size} ${PLOT.size}`} className="w-full" role="img" aria-label={t("{pairs} ta baho juftligi: tizim va o'qituvchi bahosi", { pairs: pairs.length })}>
          {ticks.map((tick) => (
            <g key={tick} className="text-muted-foreground">
              <line x1={x(0)} x2={x(100)} y1={y(tick)} y2={y(tick)} stroke="currentColor" strokeOpacity={0.15} />
              <line x1={x(tick)} x2={x(tick)} y1={y(0)} y2={y(100)} stroke="currentColor" strokeOpacity={0.15} />
              <text x={x(0) - 6} y={y(tick)} dy="0.32em" textAnchor="end" fontSize={10} fill="currentColor">
                {tick}
              </text>
              <text x={x(tick)} y={y(0) + 14} textAnchor="middle" fontSize={10} fill="currentColor">
                {tick}
              </text>
            </g>
          ))}
          {/* To'liq moslik chizig'i */}
          <line x1={x(0)} y1={y(0)} x2={x(100)} y2={y(100)} className="text-muted-foreground" stroke="currentColor" strokeDasharray="4 4" />
          {pairs.map((pair, index) => (
            <circle
              key={index}
              cx={x(pair.teacher)}
              cy={y(pair.system)}
              r={hover === index ? 6 : 4.5}
              fill="var(--series-1)"
              fillOpacity={0.75}
              stroke="var(--background)"
              strokeWidth={2}
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
          {/* Kattaroq ko'rinmas nishon: kichik nuqtaga sichqoncha tushirish oson bo'lsin */}
          {pairs.map((pair, index) => (
            <circle
              key={`hit-${index}`}
              cx={x(pair.teacher)}
              cy={y(pair.system)}
              r={10}
              fill="transparent"
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
            />
          ))}
        </svg>
        {active ? (
          <div
            className="pointer-events-none absolute rounded-md border bg-popover px-2 py-1 text-xs shadow-sm"
            style={{ left: `${(x(active.teacher) / PLOT.size) * 100}%`, top: `${(y(active.system) / PLOT.size) * 100}%`, transform: 'translate(-50%, calc(-100% - 10px))' }}
          >
            <div className="tabular-nums">{t("O'qituvchi: {teacher}", { teacher: active.teacher })}</div>
            <div className="tabular-nums">{t('Tizim: {system}', { system: active.system })}</div>
            <div className="text-muted-foreground">{GRADE_SOURCE_LABELS[active.source]}</div>
          </div>
        ) : null}
      </div>
      <figcaption className="text-center text-xs text-muted-foreground">
        {t("Gorizontal — o'qituvchi bahosi, vertikal — tizim bahosi. Uzuq chiziqdan yuqoridagi nuqtalarda tizim yumshoqroq, pastdagilarida qattiqroq baholagan.")}
      </figcaption>
    </figure>
  )
}

function SourceRow({ label, stats }: { label: string; stats: AgreementStats }) {
  return (
    <TableRow>
      <TableCell>{label}</TableCell>
      <TableCell className="text-right tabular-nums">{stats.count}</TableCell>
      <TableCell className="text-right tabular-nums">{formatNumber(stats.pearson_r)}</TableCell>
      <TableCell className="text-right tabular-nums">{formatNumber(stats.weighted_kappa)}</TableCell>
      <TableCell className="text-right tabular-nums">{formatNumber(stats.mean_abs_diff, 1)}</TableCell>
      <TableCell className="text-right tabular-nums">{formatNumber(stats.mean_diff, 1)}</TableCell>
    </TableRow>
  )
}

function AgreementCard({ labId }: { labId: string }) {
  const agreement = useQuery({
    queryKey: ['blind-review', 'agreement', labId],
    queryFn: () => api<Agreement>(`/labs/blind-review/agreement/${labQuery(labId)}`),
  })

  let content
  if (agreement.isPending) content = <ListSkeleton rows={2} />
  else if (agreement.isError) content = <ErrorState error={agreement.error} onRetry={() => void agreement.refetch()} />
  else if (!agreement.data.overall.count) content = <p className="text-sm text-muted-foreground">{t("Hali baholangan ish yo'q.")}</p>
  else {
    const { overall, by_source: bySource, pairs, bands } = agreement.data
    const loa = overall.limits_of_agreement
    content = (
      <div className="grid gap-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label={t('Korrelyatsiya (Pirson r)')}
            value={formatNumber(overall.pearson_r)}
            hint={
              t('{count} ta juftlik', { count: overall.count }) +
              (overall.count < MIN_RELIABLE_PAIRS
                ? ' · ' + t('ishonchli xulosa uchun kamida {min}', { min: MIN_RELIABLE_PAIRS })
                : '')
            }
          />
          <StatTile
            label={t('Kohen kappasi (vaznli)')}
            value={formatNumber(overall.weighted_kappa)}
            hint={kappaLabel(overall.weighted_kappa) || t("5 ballik baholar bo'yicha")}
          />
          <StatTile
            label={t("O'rtacha farq")}
            value={`${(overall.mean_diff ?? 0) > 0 ? '+' : ''}${formatNumber(overall.mean_diff, 1)}`}
            hint={
              loa ? t('95% farqlar: {value} … {value2} ball', { value: loa[0], value2: loa[1] }) : t("tizim − o'qituvchi")
            }
          />
          <StatTile
            label={t('Baho bir xil')}
            value={formatShare(overall.band_agreement)}
            hint={t('±10 ball ichida: {within_10}', { within_10: formatShare(overall.within_10) })}
          />
        </div>
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
          <ScatterPlot pairs={pairs} />
          <div className="grid gap-3">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('Tizim bahosi manbasi')}</TableHead>
                  <TableHead className="text-right">{t('Juftlik')}</TableHead>
                  <TableHead className="text-right">{t('r')}</TableHead>
                  <TableHead className="text-right">{t('Kappa')}</TableHead>
                  <TableHead className="text-right">{t("O'rt. |farq|")}</TableHead>
                  <TableHead className="text-right">{t("O'rt. farq")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <SourceRow label={t('Hammasi')} stats={overall} />
                <SourceRow label={GRADE_SOURCE_LABELS.ai} stats={bySource.ai} />
                <SourceRow label={GRADE_SOURCE_LABELS.auto} stats={bySource.auto} />
              </TableBody>
            </Table>
            <p className="text-xs text-muted-foreground">
              {t("O'rtacha ball: tizim {system_mean}, o'qituvchi {teacher_mean}. Farq musbat bo'lsa, tizim yumshoqroq baholagan. 5 ballik baho:", { system_mean: formatNumber(overall.system_mean, 1), teacher_mean: formatNumber(overall.teacher_mean, 1) })}{' '}
              {t('{bands}. Kappa: 0,6 dan yuqori — yuqori, 0,8 dan yuqori — juda yuqori moslik. Juftliklar anonim eksportda (baholash_mosligi.csv) ham bor.', { bands: bands.map((band) => `${band.min}+ → ${band.mark}`).join(', ') })}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("Tizim va o'qituvchi baholari mosligi")}</CardTitle>
        <CardDescription>
          {t("Siz baholagan ishlar uchun: baho qo'yilgan paytdagi tizim (AI yoki avtomatik tekshiruv) bahosi bilan solishtiriladi.")}
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}

export function BlindReviewPage() {
  const [labId, setLabId] = useState('')
  const labs = useQuery({ queryKey: ['labs'], queryFn: () => api<Lab[]>('/labs/') })

  return (
    <>
      <PageHeader
        title={t("Ko'r baholash")}
        description={t("Talabalar ishini ismini va tizim bahosini ko'rmasdan baholang. Keyin AI bahosi siznikiga qanchalik yaqinligi hisoblanadi.")}
      />
      <div className="mb-4">
        <label className="grid w-full max-w-sm gap-1 text-sm">
          <span className="text-xs text-muted-foreground">{t('Laboratoriya')}</span>
          <select className="h-10 w-full min-w-0 rounded-md border bg-background px-2 text-sm" value={labId} onChange={(event) => setLabId(event.target.value)}>
            <option value="">{t('Barcha laboratoriyalar')}</option>
            {(labs.data ?? []).map((lab) => (
              <option key={lab.id} value={lab.id}>
                {lab.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="grid gap-6">
        <ReviewQueue labId={labId} />
        <AgreementCard labId={labId} />
      </div>
    </>
  )
}
