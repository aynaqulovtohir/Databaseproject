import { useQuery } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { useState } from 'react'

import { TestRow } from '@/components/ExperimentCard'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { ErChiTest, ErProcessStatistics, ExperimentCohort } from '@/lib/types'

const COHORTS: { key: ExperimentCohort; color: string }[] = [
  { key: 'experimental', color: 'var(--series-1)' },
  { key: 'control', color: 'var(--series-2)' },
]
const CHART = { width: 640, height: 220, left: 40, right: 12, top: 12, bottom: 28 }

function share(value: number | null) {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function pText(p: number) {
  return p < 0.001 ? 'p < 0.001' : `p = ${p.toFixed(3)}`
}

function ChiLine({ title, test }: { title: string; test: ErChiTest | null }) {
  return (
    <li>
      <span className="font-medium">{title}: </span>
      {test ? (
        <>
          χ²({test.df}) = {test.chi2.toFixed(2)}, {pText(test.p)}, Kramer V = {test.cramers_v.toFixed(2)}
          {test.effect_label ? ` (${test.effect_label})` : ''} — {test.significant ? 'ahamiyatli' : 'ahamiyatsiz'}
          {test.reliable ? '' : ' · kutilgan son 5 dan kam, natija taxminiy'}
        </>
      ) : (
        <span className="text-muted-foreground">ma'lumot kam</span>
      )}
    </li>
  )
}

/** Tajriba va nazorat guruhlarining o'rtacha yaqinlashish egri chiziqlari (vaqt normallashtirilgan) */
function CurvesChart({ data }: { data: ErProcessStatistics }) {
  const plotWidth = CHART.width - CHART.left - CHART.right
  const plotHeight = CHART.height - CHART.top - CHART.bottom
  const series = COHORTS.filter((item) => data.cohort_comparison.curves[item.key].n > 0)
  const x = (index: number, total: number) => CHART.left + (index / Math.max(1, total - 1)) * plotWidth
  const y = (value: number) => CHART.top + plotHeight - value * plotHeight

  return (
    <div className="grid gap-2">
      <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground" aria-label="Belgilar">
        {series.map((item) => (
          <li key={item.key} className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ background: item.color }} aria-hidden="true" />
            {data.cohorts[item.key]} (n = {data.cohort_comparison.curves[item.key].n})
          </li>
        ))}
      </ul>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${CHART.width} ${CHART.height}`}
          className="w-full min-w-[30rem]"
          role="img"
          aria-label="Namunaga moslik: ishlash vaqtining ulushi bo'yicha"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
            <g key={tick} className="text-muted-foreground">
              <line x1={CHART.left} x2={CHART.left + plotWidth} y1={y(tick)} y2={y(tick)} stroke="currentColor" strokeOpacity={0.15} />
              <text x={CHART.left - 6} y={y(tick)} dy="0.32em" textAnchor="end" fontSize={11} fill="currentColor">
                {tick * 100}%
              </text>
            </g>
          ))}
          {[0, 0.5, 1].map((tick) => (
            <text
              key={tick}
              x={CHART.left + tick * plotWidth}
              y={CHART.height - 8}
              textAnchor={tick === 0 ? 'start' : tick === 1 ? 'end' : 'middle'}
              fontSize={11}
              className="fill-muted-foreground"
            >
              {tick === 0 ? 'boshlanishi' : tick === 1 ? 'oxiri' : 'yarmi'}
            </text>
          ))}
          {series.map((item) => {
            const points = data.cohort_comparison.curves[item.key].points
            const path = points.map((value, index) => `${index ? 'L' : 'M'}${x(index, points.length)},${y(value)}`).join('')
            return <path key={item.key} d={path} fill="none" stroke={item.color} strokeWidth={2} strokeLinejoin="round" />
          })}
        </svg>
      </div>
    </div>
  )
}

/** Tadqiqot: ER-diagramma chizish jarayoni — strategiyalar, AI ta'siri va strategiya o'zgarishi */
export function ErProcessStatisticsCard({ groupId }: { groupId: string }) {
  const [labId, setLabId] = useState('')
  const statistics = useQuery({
    queryKey: ['er-process-statistics', groupId, labId],
    queryFn: () => {
      const params = new URLSearchParams()
      if (groupId) params.set('group', groupId)
      if (labId) params.set('lab', labId)
      return api<ErProcessStatistics>(`/statistics/er-process/?${params}`)
    },
    placeholderData: (previous) => previous,
  })

  let content
  if (statistics.isPending) {
    content = <ListSkeleton rows={3} />
  } else if (statistics.isError) {
    content = <ErrorState error={statistics.error} onRetry={() => void statistics.refetch()} />
  } else if (!statistics.data.works) {
    content = (
      <EmptyState
        icon={History}
        title="Chizish jarayoni hali yozilmagan"
        description="Talabalar ER laboratoriyalarini bajargach (tadqiqotga rozi bo'lganlari) shu yerda tahlil paydo bo'ladi."
      />
    )
  } else {
    const data = statistics.data
    const { strategies, cohort_comparison: comparison, transitions } = data
    content = (
      <div className="grid gap-6">
        <div className="grid gap-1 text-sm">
          <p className="text-muted-foreground">
            {data.works} ta ish, {data.students} ta talaba.
          </p>
          <ul className="list-disc space-y-0.5 pl-5">
            {data.conclusions.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>

        <section className="grid gap-2">
          <h3 className="text-sm font-medium">Strategiyalar va natija</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Strategiya</TableHead>
                <TableHead className="text-right">Ishlar</TableHead>
                <TableHead className="text-right">Tajriba</TableHead>
                <TableHead className="text-right">Nazorat</TableHead>
                <TableHead className="text-right">O'rtacha baho</TableHead>
                <TableHead className="text-right">Yechganlar</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {strategies.items.map((item) => (
                <TableRow key={item.strategy}>
                  <TableCell className="max-w-72 whitespace-normal">{item.label}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {item.count} <span className="text-muted-foreground">({share(item.share)})</span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{item.by_cohort.experimental}</TableCell>
                  <TableCell className="text-right tabular-nums">{item.by_cohort.control}</TableCell>
                  <TableCell className="text-right tabular-nums">{item.mean_grade ?? '—'}</TableCell>
                  <TableCell className="text-right tabular-nums">{share(item.solved_rate)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <ul className="grid gap-0.5 text-xs">
            <ChiLine title="Strategiya × yechildi" test={strategies.solved_test} />
            <li>
              <span className="font-medium">Strategiyalar bo'yicha baholar (Kraskel–Uollis): </span>
              {strategies.grade_test ? (
                <>
                  H({strategies.grade_test.df}) = {strategies.grade_test.h.toFixed(2)}, {pText(strategies.grade_test.p)}, ε² ={' '}
                  {strategies.grade_test.epsilon2.toFixed(2)}
                  {strategies.grade_test.effect_label ? ` (${strategies.grade_test.effect_label})` : ''} —{' '}
                  {strategies.grade_test.significant ? 'ahamiyatli' : 'ahamiyatsiz'}
                </>
              ) : (
                <span className="text-muted-foreground">ma'lumot kam (kamida ikki strategiyada 3 tadan baho)</span>
              )}
            </li>
            <ChiLine title="Strategiya × guruh (AI ta'siri)" test={strategies.cohort_test} />
          </ul>
        </section>

        <section className="grid gap-2">
          <h3 className="text-sm font-medium">Namunaga yaqinlashish: tajriba va nazorat guruhlari</h3>
          <p className="text-xs text-muted-foreground">
            Har bir ishning vaqti 0–100% ga keltirilgan; chiziq — shu paytgacha erishilgan moslikning o'rtachasi.
          </p>
          <CurvesChart data={data} />
        </section>

        <section className="grid gap-2">
          <h3 className="text-sm font-medium">Jarayon ko'rsatkichlari: tajriba va nazorat</h3>
          <p className="text-xs text-muted-foreground">
            Har bir talaba bitta kuzatuv (bir nechta laboratoriyada ishlagan bo'lsa, o'rtachasi). Mezon taqsimot va
            dispersiyalarga qarab avtomatik tanlanadi.
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ko'rsatkich</TableHead>
                <TableHead>Mezon</TableHead>
                <TableHead className="text-right">Statistika</TableHead>
                <TableHead className="text-right">p</TableHead>
                <TableHead className="text-right">Effekt</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {comparison.comparisons.map((item) => (
                <TestRow
                  key={item.metric}
                  title={
                    <>
                      <div>{item.label}</div>
                      <div className="text-xs font-normal text-muted-foreground tabular-nums">
                        tajriba {item.experimental.mean ?? '—'} (n = {item.experimental.n}) · nazorat {item.control.mean ?? '—'} (n ={' '}
                        {item.control.n})
                      </div>
                    </>
                  }
                  test={item.test}
                />
              ))}
            </TableBody>
          </Table>
        </section>

        <section className="grid gap-2">
          <h3 className="text-sm font-medium">Strategiya o'zgarishi: birinchi → oxirgi laboratoriya</h3>
          {transitions.students ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Birinchisida \ oxirgisida</TableHead>
                  {transitions.strategies.map((item) => (
                    <TableHead key={item.strategy} className="max-w-40 text-right whitespace-normal">
                      {item.label}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {transitions.strategies.map((item, row) => (
                  <TableRow key={item.strategy}>
                    <TableCell className="max-w-56 whitespace-normal">{item.label}</TableCell>
                    {transitions.matrix[row].map((count, column) => (
                      <TableCell key={column} className={`text-right tabular-nums ${row === column ? 'font-medium' : ''}`}>
                        {count}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">Kamida ikkita ER laboratoriyasida ishlagan talaba hali yo'q.</p>
          )}
        </section>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1.5">
          <CardTitle>ER-diagramma chizish jarayoni</CardTitle>
          <CardDescription>
            Talabalar qanday strategiya bilan loyihalaydi, AI jarayonni qanday o'zgartiradi. Faqat tadqiqotga rozi
            bo'lgan talabalar.
          </CardDescription>
        </div>
        {statistics.data && statistics.data.labs.length > 1 ? (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Laboratoriya</span>
            <select className="h-10 rounded-md border bg-background px-2" value={labId} onChange={(event) => setLabId(event.target.value)}>
              <option value="">Barcha ER laboratoriyalari</option>
              {statistics.data.labs.map((lab) => (
                <option key={lab.id} value={lab.id}>
                  {lab.title}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
