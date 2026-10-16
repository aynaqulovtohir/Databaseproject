import { useQuery } from '@tanstack/react-query'
import { BarChart3 } from 'lucide-react'
import { useState } from 'react'

import { GroupMasteryCard } from '@/components/LearningPath'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { AiEffectBucket, LearningCurvePoint, Statistics, StatisticsGroup } from '@/lib/types'

// Diagramma ranglari index.css dagi --series-* tokenlaridan (yorug' va qorong'i mavzu uchun alohida)
const SERIES_1 = 'var(--series-1)'
const SERIES_2 = 'var(--series-2)'
const SERIES_3 = 'var(--series-3)'

function formatPercent(value: number | null) {
  return value === null ? '—' : `${value}%`
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  )
}

/** Gorizontal ustun: uzunligi qiymatga mutanosib, qiymat yonida yoziladi (rangga tayanmaydi) */
function HorizontalBar({ value, max, color, label }: { value: number; max: number; color: string; label: string }) {
  // Nol qiymat chizilmaydi (aks holda kichik ustun "bor" bo'lib ko'rinadi); kichik musbat qiymat ko'rinadigan qilinadi
  const width = max && value > 0 ? Math.max(2, (value / max) * 100) : 0
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2" title={label}>
      <div className="h-3.5 min-w-0 flex-1">
        <div className="h-full rounded-r" style={{ width: `${width}%`, background: color }} />
      </div>
    </div>
  )
}

function ErrorsCard({ errors }: { errors: Statistics['top_errors'] }) {
  const max = Math.max(0, ...errors.map((item) => item.count))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Eng ko'p uchragan xatolar</CardTitle>
        <CardDescription>
          Noto'g'ri urinishlardagi xato turlari: har bir urinishda har bir tur bir marta sanaladi.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {errors.length ? (
          <ol className="grid gap-2" aria-label="Xato turlari va soni">
            {errors.map((item) => (
              <li key={item.category} className="grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)_3rem] items-center gap-3 text-sm">
                <span className="truncate" title={item.label}>
                  {item.label}
                </span>
                <HorizontalBar value={item.count} max={max} color={SERIES_1} label={`${item.label}: ${item.count} ta`} />
                <span className="text-right tabular-nums">{item.count}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">Hali xato urinishlar yo'q.</p>
        )}
      </CardContent>
    </Card>
  )
}

function LabsCard({ labs }: { labs: Statistics['labs'] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Laboratoriyalar qiyinligi</CardTitle>
        <CardDescription>
          Yechganlar ulushi qancha past va yechish uchun urinishlar qancha ko'p bo'lsa, laboratoriya shuncha qiyin.
          Laboratoriyalar talabalar bajargan tartibda.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {labs.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Laboratoriya</TableHead>
                <TableHead className="w-[30%]">Yechganlar</TableHead>
                <TableHead className="text-right">Yechish uchun o'rtacha urinish</TableHead>
                <TableHead className="text-right">O'rtacha baho</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {labs.map((lab) => (
                <TableRow key={lab.id}>
                  <TableCell className="max-w-72 truncate font-medium" title={lab.title}>
                    {lab.title}
                    {lab.kind !== 'sql' ? (
                      <Badge variant="outline" className="ml-2">
                        {lab.kind === 'er' ? 'ER' : 'NF'}
                      </Badge>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <HorizontalBar
                        value={lab.solved_rate ?? 0}
                        max={100}
                        color={SERIES_1}
                        label={`${lab.solved} / ${lab.students} talaba yechgan`}
                      />
                      <span className="w-24 shrink-0 text-right text-xs tabular-nums">
                        {formatPercent(lab.solved_rate)} ({lab.solved}/{lab.students})
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{lab.attempts_to_solve ?? '—'}</TableCell>
                  <TableCell className="text-right tabular-nums">{lab.average_grade ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">Bu guruhlarga hali laboratoriya berilmagan.</p>
        )}
      </CardContent>
    </Card>
  )
}

const CURVE_SERIES = [
  { key: 'ai', label: 'AI yoqilgan', color: SERIES_1 },
  { key: 'control', label: 'Nazorat', color: SERIES_2 },
] as const
const CURVE = { width: 640, height: 240, left: 36, right: 84, top: 12, bottom: 28 }

/** O'rganish egri chizig'i: har bir laboratoriyani yechish uchun o'rtacha urinishlar (kamaysa — o'rganish tezlashgan) */
function LearningCurveChart({ points }: { points: LearningCurvePoint[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const series = CURVE_SERIES.filter((item) => points.some((point) => point[item.key].students > 0))
  const values = points.flatMap((point) => series.map((item) => point[item.key].attempts_to_solve ?? 0))
  const top = Math.max(2, Math.ceil(Math.max(...values)))
  const plotWidth = CURVE.width - CURVE.left - CURVE.right
  const plotHeight = CURVE.height - CURVE.top - CURVE.bottom
  const x = (index: number) => CURVE.left + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth)
  const y = (value: number) => CURVE.top + plotHeight - (value / top) * plotHeight
  const step = top <= 5 ? 1 : Math.ceil(top / 5)
  const ticks = Array.from({ length: Math.floor(top / step) + 1 }, (_, index) => index * step)
  const active = hover === null ? null : points[hover]

  /** Bo'sh qiymatlarda chiziq uziladi */
  function path(key: 'ai' | 'control') {
    let d = ''
    let open = false
    points.forEach((point, index) => {
      const value = point[key].attempts_to_solve
      if (value === null) {
        open = false
        return
      }
      d += `${open ? 'L' : 'M'}${x(index)},${y(value)}`
      open = true
    })
    return d
  }

  function lastLabel(key: 'ai' | 'control') {
    for (let index = points.length - 1; index >= 0; index -= 1) {
      const value = points[index][key].attempts_to_solve
      if (value !== null) return { index, value }
    }
    return null
  }

  return (
    <div className="grid gap-3">
      <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Belgilar">
        {series.map((item) => (
          <li key={item.key} className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ background: item.color }} aria-hidden="true" />
            {item.label} guruhlar
          </li>
        ))}
      </ul>
      {/* Telefonda yozuvlar mayda bo'lib ketmasligi uchun grafik eni saqlanadi va gorizontal suriladi */}
      <div className="overflow-x-auto">
        <div className="relative min-w-[34rem]">
          <svg
            viewBox={`0 0 ${CURVE.width} ${CURVE.height}`}
            className="w-full"
            role="img"
            aria-label="Laboratoriyalar bo'yicha yechish uchun o'rtacha urinishlar"
            onMouseLeave={() => setHover(null)}
          >
            {ticks.map((tick) => (
              <g key={tick} className="text-muted-foreground">
                <line x1={CURVE.left} x2={CURVE.left + plotWidth} y1={y(tick)} y2={y(tick)} stroke="currentColor" strokeOpacity={0.15} />
                <text x={CURVE.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" fontSize={11} fill="currentColor">
                  {tick}
                </text>
              </g>
            ))}
            {points.map((point, index) => (
              <text key={point.id} x={x(index)} y={CURVE.height - 8} textAnchor="middle" fontSize={11} className="fill-muted-foreground">
                {point.position}
              </text>
            ))}
            {active !== null && hover !== null ? (
              <line x1={x(hover)} x2={x(hover)} y1={CURVE.top} y2={CURVE.top + plotHeight} className="stroke-muted-foreground" strokeOpacity={0.5} />
            ) : null}
            {series.map((item) => (
              <g key={item.key}>
                <path d={path(item.key)} fill="none" stroke={item.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                {points.map((point, index) => {
                  const value = point[item.key].attempts_to_solve
                  return value === null ? null : (
                    <circle
                      key={point.id}
                      cx={x(index)}
                      cy={y(value)}
                      r={hover === index ? 5 : 4}
                      fill={item.color}
                      stroke="var(--card)"
                      strokeWidth={2}
                    />
                  )
                })}
                {(() => {
                  const last = lastLabel(item.key)
                  return last ? (
                    <text x={x(last.index) + 10} y={y(last.value)} dy="0.32em" fontSize={11} className="fill-foreground">
                      {item.label}
                    </text>
                  ) : null
                })()}
              </g>
            ))}
            {/* Hover nishonlari: har bir laboratoriya ustuni bo'yicha */}
            {points.map((point, index) => (
              <rect
                key={point.id}
                x={x(index) - plotWidth / Math.max(1, points.length - 1) / 2}
                y={CURVE.top}
                width={plotWidth / Math.max(1, points.length - 1)}
                height={plotHeight}
                fill="transparent"
                onMouseEnter={() => setHover(index)}
              />
            ))}
          </svg>
          {active !== null && hover !== null ? (
            <div
              className="pointer-events-none absolute top-0 z-10 w-56 rounded-md border bg-popover p-2 text-xs shadow-sm"
              style={{
                left: `${(x(hover) / CURVE.width) * 100}%`,
                transform: hover > points.length / 2 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)',
              }}
            >
              <div className="mb-1 font-medium">
                {active.position}. {active.title}
              </div>
              {series.map((item) => {
                const segment = active[item.key]
                return (
                  <div key={item.key} className="flex items-start gap-1.5">
                    <span className="mt-1 size-2 shrink-0 rounded-full" style={{ background: item.color }} aria-hidden="true" />
                    <span>
                      {item.label}: {segment.attempts_to_solve ?? '—'} urinish
                      <span className="block text-muted-foreground">
                        {segment.solved}/{segment.students} yechgan · birinchi urinishda {formatPercent(segment.first_try_rate)}
                      </span>
                    </span>
                  </div>
                )
              })}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function LearningCurveCard({ points }: { points: LearningCurvePoint[] }) {
  const hasData = points.some((point) => point.ai.attempts_to_solve !== null || point.control.attempts_to_solve !== null)
  return (
    <Card>
      <CardHeader>
        <CardTitle>O'rganish egri chizig'i</CardTitle>
        <CardDescription>
          Laboratoriyalar talabalar bajargan tartibda (gorizontal o'qda tartib raqami). Vertikal o'q — yechgan talabalarning
          birinchi to'g'ri yechimgacha o'rtacha urinishlari. Egri chiziq pasaysa, talabalar tezroq o'rganmoqda.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {hasData ? <LearningCurveChart points={points} /> : <p className="text-sm text-muted-foreground">Hali yechilgan laboratoriya yo'q.</p>}
        {points.length ? (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">Jadval ko'rinishida</summary>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>№</TableHead>
                  <TableHead>Laboratoriya</TableHead>
                  {CURVE_SERIES.map((item) => (
                    <TableHead key={item.key} className="text-right">
                      {item.label}: urinish (yechgan)
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {points.map((point) => (
                  <TableRow key={point.id}>
                    <TableCell className="tabular-nums">{point.position}</TableCell>
                    <TableCell className="max-w-72 truncate" title={point.title}>
                      {point.title}
                    </TableCell>
                    {CURVE_SERIES.map((item) => (
                      <TableCell key={item.key} className="text-right tabular-nums">
                        {point[item.key].attempts_to_solve ?? '—'} ({point[item.key].solved}/{point[item.key].students})
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </details>
        ) : null}
      </CardContent>
    </Card>
  )
}

function AiBucket({ title, bucket, color }: { title: string; bucket: AiEffectBucket; color: string }) {
  return (
    <div className="grid gap-2">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span>{title}</span>
        <span className="text-xl font-semibold tabular-nums">{formatPercent(bucket.rate)}</span>
      </div>
      <HorizontalBar value={bucket.rate ?? 0} max={100} color={color} label={`${bucket.solved} / ${bucket.pairs}`} />
      <span className="text-xs text-muted-foreground tabular-nums">
        {bucket.solved} / {bucket.pairs} holatda keyin to'g'ri yechilgan
      </span>
    </div>
  )
}

function AiEffectCard({ effect }: { effect: Statistics['ai_effect'] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI maslahatining ta'siri</CardTitle>
        <CardDescription>
          Xato qilgan talaba laboratoriyani keyinroq to'g'ri yechdimi: AI maslahatini olganlar va olmaganlar
          (nazorat guruhi ham shu yerda) taqqoslanadi.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-2">
        <AiBucket title="AI maslahatini olgan" bucket={effect.with_advice} color={SERIES_1} />
        <AiBucket title="Maslahatsiz" bucket={effect.without_advice} color={SERIES_2} />
      </CardContent>
    </Card>
  )
}

function TestBars({ group, max }: { group: StatisticsGroup; max: number }) {
  const bars = [
    { key: 'pre', label: 'Kirish', value: group.pre_test, count: group.pre_count, color: SERIES_1 },
    { key: 'post', label: 'Chiqish', value: group.post_test, count: group.post_count, color: SERIES_2 },
    // Kechiktirilgan test o'tkazilgan bo'lsagina ko'rsatiladi
    ...(group.delayed_count
      ? [{ key: 'delayed', label: 'Keyin', value: group.delayed_test, count: group.delayed_count, color: SERIES_3 }]
      : []),
  ]
  return (
    <div className="grid gap-0.5">
      {bars.map((bar) => (
        <div key={bar.key} className="flex items-center gap-2">
          <span className="w-14 shrink-0 text-xs text-muted-foreground">{bar.label}</span>
          {bar.value === null ? (
            <span className="text-xs text-muted-foreground">hali topshirilmagan</span>
          ) : (
            <>
              <HorizontalBar value={bar.value} max={max} color={bar.color} label={`${bar.label} testi: ${bar.value}% (${bar.count} ta talaba)`} />
              <span className="w-12 shrink-0 text-right text-xs tabular-nums">{bar.value}%</span>
            </>
          )}
        </div>
      ))}
    </div>
  )
}

function GroupsCard({ groups }: { groups: StatisticsGroup[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Guruhlar taqqoslashi</CardTitle>
        <CardDescription>
          Kirish, chiqish va kechiktirilgan (kurs tugagandan keyin) testlarning o'rtacha natijasi (%) va o'sish. Tajriba
          guruhida AI yoqilgan, nazorat guruhida o'chirilgan.
        </CardDescription>
        <ul className="flex flex-wrap gap-4 pt-1 text-xs text-muted-foreground" aria-label="Belgilar">
          <li className="flex items-center gap-1.5">
            <span className="size-3 rounded-sm" style={{ background: SERIES_1 }} aria-hidden="true" /> Kirish testi
          </li>
          <li className="flex items-center gap-1.5">
            <span className="size-3 rounded-sm" style={{ background: SERIES_2 }} aria-hidden="true" /> Chiqish testi
          </li>
          {groups.some((group) => group.delayed_count) ? (
            <li className="flex items-center gap-1.5">
              <span className="size-3 rounded-sm" style={{ background: SERIES_3 }} aria-hidden="true" /> Kechiktirilgan test
            </li>
          ) : null}
        </ul>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Guruh</TableHead>
              <TableHead className="w-[34%]">Testlar (o'rtacha %)</TableHead>
              <TableHead className="text-right">O'sish</TableHead>
              <TableHead className="text-right">Laboratoriyalarni yechgan</TableHead>
              <TableHead className="text-right">O'rtacha baho</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.map((group) => (
              <TableRow key={group.id}>
                <TableCell>
                  <div className="font-medium">{group.name}</div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    {group.ai_enabled ? (
                      <Badge variant="outline">AI yoqilgan</Badge>
                    ) : (
                      <Badge className="bg-amber-100 text-amber-800">AI o'chirilgan</Badge>
                    )}
                    {group.students} talaba
                  </div>
                </TableCell>
                <TableCell>
                  <TestBars group={group} max={100} />
                </TableCell>
                <TableCell className="text-right font-medium tabular-nums">
                  {group.gain === null ? '—' : `${group.gain > 0 ? '+' : ''}${group.gain}`}
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatPercent(group.solved_rate)}</TableCell>
                <TableCell className="text-right tabular-nums">{group.average_grade ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function StatisticsPage() {
  const [groupId, setGroupId] = useState('')
  const statistics = useQuery({
    queryKey: ['statistics', groupId],
    queryFn: () => api<Statistics>(`/statistics/${groupId ? `?group=${groupId}` : ''}`),
    placeholderData: (previous) => previous,
  })

  let content
  if (statistics.isPending) {
    content = <ListSkeleton />
  } else if (statistics.isError) {
    content = <ErrorState error={statistics.error} onRetry={() => void statistics.refetch()} />
  } else if (!statistics.data.groups.length) {
    content = (
      <EmptyState icon={BarChart3} title="Hali guruh yo'q" description="Statistika guruhlaringiz talabalari bo'yicha hisoblanadi." />
    )
  } else {
    const data = statistics.data
    content = (
      <div className="grid gap-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile label="Talabalar" value={String(data.overview.students)} />
          <StatTile label="Laboratoriya urinishlari" value={String(data.overview.attempts)} hint={`${data.overview.labs} ta laboratoriya`} />
          <StatTile label="Yechilgan laboratoriyalar" value={formatPercent(data.overview.solved_rate)} hint="talaba va laboratoriya juftliklaridan" />
          <StatTile label="O'rtacha baho" value={data.overview.average_grade === null ? '—' : String(data.overview.average_grade)} hint="100 ballik" />
        </div>
        <GroupsCard groups={data.groups} />
        <LearningCurveCard points={data.learning_curve} />
        <div className="grid items-start gap-4 xl:grid-cols-2">
          <ErrorsCard errors={data.top_errors} />
          <AiEffectCard effect={data.ai_effect} />
        </div>
        <LabsCard labs={data.labs} />
        {groupId ? <GroupMasteryCard groupId={groupId} /> : null}
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Statistika"
        description="Tajriba natijalari: guruhlar, xatolar, laboratoriyalar qiyinligi va AI ta'siri. To'liq ma'lumot — Virtual laboratoriya sahifasidagi «Tadqiqot ma'lumotlari»."
        actions={
          statistics.data?.groups_available.length ? (
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Guruh</span>
              <select
                className="h-10 rounded-md border bg-background px-2"
                value={groupId}
                onChange={(event) => setGroupId(event.target.value)}
              >
                <option value="">Barcha guruhlar</option>
                {statistics.data.groups_available.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null
        }
      />
      {content}
    </>
  )
}
