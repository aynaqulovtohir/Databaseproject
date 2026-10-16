import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { PageHeader } from '@/components/PageHeader'
import { ErrorState, ListSkeleton } from '@/components/States'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { AIUsageReport, AIUsageTotals } from '@/lib/types'

const PERIODS = [7, 30, 90]
const numberFormat = new Intl.NumberFormat('uz-UZ')

function formatTokens(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)} mln`
  if (value >= 10_000) return `${Math.round(value / 1000)} ming`
  return numberFormat.format(value)
}

function formatCost(value: number) {
  return `$${value < 1 ? value.toFixed(3) : value.toFixed(2)}`
}

function UsageTile({ label, totals, priced }: { label: string; totals: AIUsageTotals; priced: boolean }) {
  const tokens = totals.input_tokens + totals.output_tokens
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{priced ? formatCost(totals.cost) : formatTokens(tokens)}</div>
      <div className="mt-1 text-xs text-muted-foreground tabular-nums">
        {priced ? `${formatTokens(tokens)} token · ` : 'token · '}
        {numberFormat.format(totals.requests)} so'rov
        {totals.failed ? ` · ${numberFormat.format(totals.failed)} xato` : ''}
      </div>
    </div>
  )
}

/** Kunlik tokenlar: bitta seriyali ustunli diagramma, har bir ustunda tooltip */
function DailyChart({ daily, priced }: { daily: AIUsageReport['daily']; priced: boolean }) {
  const [hover, setHover] = useState<number | null>(null)
  const totals = daily.map((day) => day.input_tokens + day.output_tokens)
  const max = Math.max(1, ...totals)
  const width = 640
  const height = 180
  const bottom = 20
  const slot = width / daily.length
  const barWidth = Math.max(2, Math.min(24, slot - 2))
  const active = hover === null ? null : daily[hover]
  const labelEvery = Math.ceil(daily.length / 8)

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Kunlik AI tokenlari" onMouseLeave={() => setHover(null)}>
        <line x1={0} x2={width} y1={height - bottom} y2={height - bottom} className="stroke-border" />
        {daily.map((day, index) => {
          const barHeight = totals[index] ? Math.max(2, (totals[index] / max) * (height - bottom - 8)) : 0
          const x = index * slot + (slot - barWidth) / 2
          return (
            <g key={day.date}>
              {barHeight ? (
                <rect
                  x={x}
                  y={height - bottom - barHeight}
                  width={barWidth}
                  height={barHeight}
                  rx={Math.min(4, barWidth / 2)}
                  fill="var(--series-1)"
                  fillOpacity={hover === null || hover === index ? 1 : 0.5}
                />
              ) : null}
              {index % labelEvery === 0 ? (
                <text x={index * slot + slot / 2} y={height - 5} textAnchor="middle" fontSize={10} className="fill-muted-foreground">
                  {day.date.slice(8, 10)}.{day.date.slice(5, 7)}
                </text>
              ) : null}
              <rect x={index * slot} y={0} width={slot} height={height - bottom} fill="transparent" onMouseEnter={() => setHover(index)} />
            </g>
          )
        })}
      </svg>
      {active !== null && hover !== null ? (
        <div
          className="pointer-events-none absolute top-0 z-10 rounded-md border bg-popover p-2 text-xs shadow-sm"
          style={{
            left: `${((hover + 0.5) / daily.length) * 100}%`,
            transform: hover > daily.length / 2 ? 'translateX(calc(-100% - 8px))' : 'translateX(8px)',
          }}
        >
          <div className="font-medium">
            {active.date.slice(8, 10)}.{active.date.slice(5, 7)}.{active.date.slice(0, 4)}
          </div>
          <div className="tabular-nums">{formatTokens(active.input_tokens + active.output_tokens)} token</div>
          <div className="text-muted-foreground tabular-nums">
            {active.requests} so'rov{active.failed ? `, ${active.failed} xato` : ''}
            {priced ? ` · ${formatCost(active.cost)}` : ''}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function BreakdownTable({ rows, label, priced }: { rows: (AIUsageTotals & { name: string })[]; label: string; priced: boolean }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">Bu davrda AI so'rovi bo'lmagan.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{label}</TableHead>
          <TableHead className="text-right">So'rovlar</TableHead>
          <TableHead className="text-right">Xato</TableHead>
          <TableHead className="text-right">Kirish tokeni</TableHead>
          <TableHead className="text-right">Chiqish tokeni</TableHead>
          {priced ? <TableHead className="text-right">Xarajat</TableHead> : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.name}>
            <TableCell className="font-medium">{row.name}</TableCell>
            <TableCell className="text-right tabular-nums">{numberFormat.format(row.requests)}</TableCell>
            <TableCell className="text-right tabular-nums">{row.failed ? numberFormat.format(row.failed) : '—'}</TableCell>
            <TableCell className="text-right tabular-nums">{formatTokens(row.input_tokens)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatTokens(row.output_tokens)}</TableCell>
            {priced ? <TableCell className="text-right tabular-nums">{formatCost(row.cost)}</TableCell> : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function AIUsagePage() {
  const [days, setDays] = useState(30)
  const report = useQuery({
    queryKey: ['ai-usage', days],
    queryFn: () => api<AIUsageReport>(`/ai/usage/?days=${days}`),
    placeholderData: (previous) => previous,
  })

  let content
  if (report.isPending) content = <ListSkeleton />
  else if (report.isError) content = <ErrorState error={report.error} onRetry={() => void report.refetch()} />
  else {
    const data = report.data
    const priced = data.price.configured
    content = (
      <div className="grid gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <UsageTile label="Bugun" totals={data.today} priced={priced} />
          <UsageTile label="Shu oy" totals={data.month} priced={priced} />
          <UsageTile label="O'tgan oy" totals={data.previous_month} priced={priced} />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Kunlik sarf (oxirgi {data.days} kun)</CardTitle>
            <CardDescription>
              Jami: {formatTokens(data.period.input_tokens + data.period.output_tokens)} token, {numberFormat.format(data.period.requests)} so'rov
              {priced ? `, ${formatCost(data.period.cost)}` : ''}.{' '}
              {priced
                ? `Narx: 1 mln kirish tokeni $${data.price.input_per_mtok}, chiqish tokeni $${data.price.output_per_mtok}.`
                : "Narx sozlanmagan (bepul tarif): .env faylidagi AI_PRICE_INPUT_PER_MTOK va AI_PRICE_OUTPUT_PER_MTOK bilan pulli tarif narxini kiriting."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <DailyChart daily={data.daily} priced={priced} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Maqsad bo'yicha</CardTitle>
            <CardDescription>Qaysi imkoniyat qancha sarflayapti. Xato — AI javob bermagan yoki javobi yaroqsiz bo'lgan so'rovlar.</CardDescription>
          </CardHeader>
          <CardContent>
            <BreakdownTable rows={data.by_purpose.map((row) => ({ ...row, name: row.label }))} label="Maqsad" priced={priced} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Model bo'yicha</CardTitle>
            <CardDescription>Asosiy model band bo'lsa, so'rov zaxira modelga o'tadi.</CardDescription>
          </CardHeader>
          <CardContent>
            <BreakdownTable rows={data.by_model.map((row) => ({ ...row, name: row.model }))} label="Model" priced={priced} />
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="AI xarajati"
        description="AI so'rovlari, tokenlar va taxminiy xarajat. Talabalar matni va ismi hisobga yozilmaydi."
        actions={
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Davr</span>
            <select className="h-10 rounded-md border bg-background px-2" value={days} onChange={(event) => setDays(Number(event.target.value))}>
              {PERIODS.map((period) => (
                <option key={period} value={period}>
                  {period} kun
                </option>
              ))}
            </select>
          </label>
        }
      />
      {content}
    </>
  )
}
