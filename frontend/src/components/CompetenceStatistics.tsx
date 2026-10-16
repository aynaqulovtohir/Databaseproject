import { useQuery } from '@tanstack/react-query'
import { Copy } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { CompetenceEfficiency, CompetenceEfficiencyRow, CompetenceStage, StatDescribe } from '@/lib/types'

const STAGE_LABELS: Record<CompetenceStage, string> = {
  initial: 'Tajriba boshida',
  final: 'Tajriba oxirida',
  delayed: 'Tajribadan keyin',
}

function formatP(p: number | null | undefined) {
  if (p === null || p === undefined) return '—'
  return p < 0.001 ? '< 0,001' : p.toFixed(3).replace('.', ',')
}

/** Matn uchun: "p < 0,001" yoki "p = 0,042" */
function pText(p: number | null | undefined) {
  return p !== null && p !== undefined && p < 0.001 ? 'p < 0,001' : `p = ${formatP(p)}`
}

function num(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? '—' : value.toFixed(digits).replace('.', ',')
}

function meanSd(item: StatDescribe) {
  return item.n ? `${num(item.mean, 1)} ± ${num(item.sd, 1)}` : '—'
}

/** p-qiymat: ahamiyatli bo'lsa qalin va "ahamiyatli" belgisi bilan (rangga tayanmaydi) */
function PValue({ p, alpha }: { p: number | null | undefined; alpha: number }) {
  if (p === null || p === undefined) return <span className="text-muted-foreground">—</span>
  const significant = p < alpha
  return (
    <span className={significant ? 'font-semibold tabular-nums' : 'tabular-nums'}>
      {pText(p)}
      {significant ? <span className="sr-only"> (ahamiyatli)</span> : null}
      {significant ? <span aria-hidden="true">*</span> : null}
    </span>
  )
}

/** Dissertatsiya matni uchun tayyor xulosa jumlalari (O'zbek tilida, raqamlar vergul bilan). */
function conclusions(rows: CompetenceEfficiencyRow[], stage: CompetenceStage, alpha: number) {
  const items: string[] = []
  for (const row of rows) {
    const data = row.stages[stage]
    const tg = data.describe.experimental
    const ng = data.describe.control
    if (!tg.n || !ng.n) continue
    const test = data.t_test
    const chi = data.chi_square
    const parts = [
      `«${row.name}»: tajriba guruhida o'rtacha ball ${num(tg.mean, 1)} (SD = ${num(tg.sd, 1)}, n = ${tg.n}), nazorat guruhida ${num(ng.mean, 1)} (SD = ${num(ng.sd, 1)}, n = ${ng.n})`,
    ]
    if (test) {
      const significant = test.p < alpha
      if (stage === 'initial') {
        parts.push(
          significant
            ? `guruhlar boshlang'ich holatda statistik farq qiladi (Uelch t(${num(test.df, 1)}) = ${num(test.t)}, ${pText(test.p)}) — tanlov ekvivalent emas`
            : `boshlang'ich holatda guruhlar o'rtasida statistik ahamiyatli farq yo'q (Uelch t(${num(test.df, 1)}) = ${num(test.t)}, ${pText(test.p)}), ya'ni guruhlar teng`,
        )
      } else {
        parts.push(
          significant
            ? `farq statistik ahamiyatli (Uelch t(${num(test.df, 1)}) = ${num(test.t)}, ${pText(test.p)}; Koen d = ${num(test.cohens_d)})`
            : `farq statistik ahamiyatli emas (Uelch t(${num(test.df, 1)}) = ${num(test.t)}, ${pText(test.p)})`,
        )
      }
    }
    if (chi) {
      parts.push(
        `darajalar taqsimoti bo'yicha χ²(${chi.df}) = ${num(chi.chi2)}, ${pText(chi.p)}, Kramer V = ${num(chi.cramers_v)}${chi.reliable ? '' : ' (kutilgan sonlar 5 dan kam — natija taxminiy)'}`,
      )
    }
    if (stage !== 'initial' && data.efficiency_ratio !== null) {
      parts.push(`samaradorlik koeffitsienti K = ${num(data.efficiency_ratio)}`)
    }
    if (stage === 'delayed') {
      const { experimental, control, difference } = row.retention
      const delta = (item: typeof experimental) =>
        item.before_mean !== null && item.after_mean !== null ? num(item.after_mean - item.before_mean, 1) : '—'
      if (experimental.n && control.n) {
        const retained = difference && difference.p < alpha
        parts.push(
          `tajriba oxiridan kechiktirilgan testgacha o'zgarish: tajriba guruhida ${delta(experimental)}, nazorat guruhida ${delta(control)} ball` +
            (difference
              ? retained
                ? difference.t > 0
                  ? ` — tajriba guruhi bilimni statistik ahamiyatli darajada yaxshiroq saqlagan (Uelch t(${num(difference.df, 1)}) = ${num(difference.t)}, ${pText(difference.p)})`
                  : ` — nazorat guruhi bilimni statistik ahamiyatli darajada yaxshiroq saqlagan (Uelch t(${num(difference.df, 1)}) = ${num(difference.t)}, ${pText(difference.p)})`
                : ` — saqlanishdagi farq statistik ahamiyatli emas (${pText(difference.p)})`
              : ''),
        )
      }
    }
    items.push(`${parts.join('; ')}.`)
  }
  return items
}

function toTsv(rows: CompetenceEfficiencyRow[], stage: CompetenceStage) {
  const header = [
    'Komponent', 'TG n', 'TG M', 'TG SD', 'NG n', 'NG M', 'NG SD', 'χ²', 'df', 'p (χ²)', 'Kramer V',
    'Uelch t', 'df', 'p (t)', 'Koen d', 'Mann–Uitni U', 'p (U)', 'K',
  ]
  const lines = rows.map((row) => {
    const data = row.stages[stage]
    const { experimental: tg, control: ng } = data.describe
    return [
      row.name, tg.n, num(tg.mean, 1), num(tg.sd, 1), ng.n, num(ng.mean, 1), num(ng.sd, 1),
      num(data.chi_square?.chi2), data.chi_square?.df ?? '—', formatP(data.chi_square?.p), num(data.chi_square?.cramers_v),
      num(data.t_test?.t), num(data.t_test?.df, 1), formatP(data.t_test?.p), num(data.t_test?.cohens_d),
      num(data.mann_whitney?.u, 1), formatP(data.mann_whitney?.p), num(data.efficiency_ratio),
    ].join('\t')
  })
  return [header.join('\t'), ...lines].join('\n')
}

function ComparisonTable({ data, stage }: { data: CompetenceEfficiency; stage: CompetenceStage }) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Komponent</TableHead>
            <TableHead>Tajriba guruhi (M ± SD, n)</TableHead>
            <TableHead>Nazorat guruhi (M ± SD, n)</TableHead>
            <TableHead>Pirson χ²</TableHead>
            <TableHead>Uelch t-testi</TableHead>
            <TableHead>Mann–Uitni U</TableHead>
            {stage !== 'initial' ? <TableHead title="Tajriba guruhi o'rtachasi / nazorat guruhi o'rtachasi">K</TableHead> : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rows.map((row) => {
            const item = row.stages[stage]
            return (
              <TableRow key={row.key}>
                <TableCell className="font-medium">{row.name}</TableCell>
                <TableCell className="tabular-nums">
                  {meanSd(item.describe.experimental)} <span className="text-muted-foreground">({item.describe.experimental.n})</span>
                </TableCell>
                <TableCell className="tabular-nums">
                  {meanSd(item.describe.control)} <span className="text-muted-foreground">({item.describe.control.n})</span>
                </TableCell>
                <TableCell className="tabular-nums">
                  {item.chi_square ? (
                    <div className="grid">
                      <span>
                        χ²({item.chi_square.df}) = {num(item.chi_square.chi2)}
                        {item.chi_square.reliable ? null : (
                          <span className="text-muted-foreground" title={`Eng kichik kutilgan son ${num(item.chi_square.min_expected, 1)} — ${data.min_expected} dan kam`}>
                            {' '}†
                          </span>
                        )}
                      </span>
                      <PValue p={item.chi_square.p} alpha={data.alpha} />
                      <span className="text-xs text-muted-foreground">V = {num(item.chi_square.cramers_v)}</span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="tabular-nums">
                  {item.t_test ? (
                    <div className="grid">
                      <span>
                        t({num(item.t_test.df, 1)}) = {num(item.t_test.t)}
                      </span>
                      <PValue p={item.t_test.p} alpha={data.alpha} />
                      <span className="text-xs text-muted-foreground">d = {num(item.t_test.cohens_d)}</span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="tabular-nums">
                  {item.mann_whitney ? (
                    <div className="grid">
                      <span>
                        U = {num(item.mann_whitney.u, 1)}
                        {item.mann_whitney.approximate ? <span className="text-muted-foreground" title="Tanlanma kichik: normal yaqinlashish taxminiy"> ‡</span> : null}
                      </span>
                      <PValue p={item.mann_whitney.p} alpha={data.alpha} />
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                {stage !== 'initial' ? <TableCell className="tabular-nums">{num(item.efficiency_ratio)}</TableCell> : null}
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

/** Ikki kesim orasidagi o'zgarish: o'sish (boshi → oxiri) yoki bilim saqlanishi (oxiri → keyin) */
function ChangeTable({
  data,
  field,
  span,
  differenceLabel,
}: {
  data: CompetenceEfficiency
  field: 'growth' | 'retention'
  span: string
  differenceLabel: string
}) {
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Komponent</TableHead>
            <TableHead>Tajriba guruhi: {span}</TableHead>
            <TableHead>Nazorat guruhi: {span}</TableHead>
            <TableHead>{differenceLabel} (Uelch t)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.rows.map((row) => {
            const change = row[field]
            return (
              <TableRow key={row.key}>
                <TableCell className="font-medium">{row.name}</TableCell>
                {(['experimental', 'control'] as const).map((cohort) => {
                  const item = change[cohort]
                  return (
                    <TableCell key={cohort} className="tabular-nums">
                      {item.n ? (
                        <div className="grid">
                          <span>
                            {num(item.before_mean, 1)} → {num(item.after_mean, 1)} <span className="text-muted-foreground">(n = {item.n})</span>
                          </span>
                          {item.paired ? (
                            <>
                              <PValue p={item.paired.p} alpha={data.alpha} />
                              <span className="text-xs text-muted-foreground">
                                t({item.paired.df}) = {num(item.paired.t)}, d<sub>z</sub> = {num(item.paired.d_z)}
                              </span>
                            </>
                          ) : null}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">Ikkala kesimda o'lchanganlar yo'q</span>
                      )}
                    </TableCell>
                  )
                })}
                <TableCell className="tabular-nums">
                  {change.difference ? (
                    <div className="grid">
                      <span>t({num(change.difference.df, 1)}) = {num(change.difference.t)}</span>
                      <PValue p={change.difference.p} alpha={data.alpha} />
                      <span className="text-xs text-muted-foreground">g = {num(change.difference.hedges_g)}</span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

/** stages — modelda o'lchanadigan kesimlar (kechiktirilgan test bog'langan bo'lsa, uchta) */
export function CompetenceStatisticsCard({ stages }: { stages: CompetenceStage[] }) {
  const [stage, setStage] = useState<CompetenceStage>('final')
  const efficiency = useQuery({
    queryKey: ['competence-efficiency'],
    queryFn: () => api<CompetenceEfficiency>('/competence/efficiency/'),
  })

  let content
  if (efficiency.isPending) {
    content = <ListSkeleton />
  } else if (efficiency.isError) {
    content = <ErrorState error={efficiency.error} onRetry={() => void efficiency.refetch()} />
  } else {
    const data = efficiency.data
    const lines = conclusions(data.rows, stage, data.alpha)
    const copy = async () => {
      try {
        await navigator.clipboard.writeText(toTsv(data.rows, stage))
        toast.success("Jadval nusxalandi: Excel yoki Word jadvaliga joylashtiring.")
      } catch {
        toast.error("Nusxalab bo'lmadi: brauzer ruxsat bermadi.")
      }
    }
    content = (
      <div className="grid gap-5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex rounded-lg border p-0.5" role="group" aria-label="Kesim">
            {stages.map((item) => (
              <Button key={item} type="button" size="sm" variant={stage === item ? 'secondary' : 'ghost'} aria-pressed={stage === item} onClick={() => setStage(item)}>
                {STAGE_LABELS[item]}
              </Button>
            ))}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => void copy()}>
            <Copy aria-hidden="true" />
            Jadvalni nusxalash
          </Button>
          <span className="text-sm text-muted-foreground">
            Tajriba guruhi: {data.students.experimental} talaba · Nazorat guruhi: {data.students.control} talaba
          </span>
        </div>
        {!data.students.experimental || !data.students.control ? (
          <p className="text-sm text-muted-foreground">
            Solishtirish uchun ikkala guruh ham kerak: tajriba (AI yoqilgan) va nazorat (AI o'chirilgan). Hozir testlar hisoblanmaydi.
          </p>
        ) : null}
        <section className="grid gap-2">
          <h3 className="text-sm font-medium">Tajriba va nazorat guruhlari: {STAGE_LABELS[stage].toLowerCase()}</h3>
          <ComparisonTable data={data} stage={stage} />
        </section>
        <section className="grid gap-2">
          <h3 className="text-sm font-medium">O'sish: tajriba boshidan oxirigacha (har bir guruh ichida, juftlangan t-test)</h3>
          <ChangeTable data={data} field="growth" span="boshida → oxirida" differenceLabel="O'sishlar farqi" />
        </section>
        {stages.includes('delayed') ? (
          <section className="grid gap-2">
            <h3 className="text-sm font-medium">
              Bilim saqlanishi: tajriba oxiridan kechiktirilgan testgacha (manfiy o'zgarish — unutilgan qism)
            </h3>
            <ChangeTable data={data} field="retention" span="oxirida → keyin" differenceLabel="Saqlanish farqi" />
          </section>
        ) : null}
        {lines.length ? (
          <section className="grid gap-2">
            <h3 className="flex items-center gap-2 text-sm font-medium">
              Xulosa matni <Badge variant="outline">{STAGE_LABELS[stage]}</Badge>
            </h3>
            <ul className="grid list-disc gap-1.5 pl-5 text-sm">
              {lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        ) : null}
        <p className="text-xs text-muted-foreground">
          * — statistik ahamiyatli (p &lt; {String(data.alpha).replace('.', ',')}). † — χ² taxminiy: eng kichik kutilgan son {data.min_expected} dan kam
          (Kochran qoidasi), kichik guruhlarda Fisher aniq testini qo'llash tavsiya etiladi. ‡ — Mann–Uitni: tanlanma kichik (n &lt; 8),
          normal yaqinlashish taxminiy. Uelch t-testi dispersiyalar tengligini talab qilmaydi; taqsimot normal bo'lmasa, Mann–Uitni
          natijasiga tayaning. d — Koen d (0,2 kichik, 0,5 o'rta, 0,8 katta effekt), V — Kramer V, g — Xedjes g,
          K — samaradorlik koeffitsienti (tajriba / nazorat o'rtachasi; 1 dan katta bo'lsa, tajriba guruhi yaxshiroq).
        </p>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Statistik tahlil</CardTitle>
        <CardDescription>
          Tajriba samaradorligi: tajriba boshida guruhlar teng bo'lishi (farq ahamiyatsiz), oxirida esa tajriba guruhi ustun bo'lishi kerak.
          Faqat shu kesimda o'lchangan talabalar hisobga olinadi.
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
