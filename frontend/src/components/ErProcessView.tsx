import { useQuery } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { useState } from 'react'

import { ErEditor } from '@/components/ErEditor'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { ErProcess, ErProcessMetrics, ErProcessStep } from '@/lib/types'

const SOURCE_LABELS: Record<ErProcessStep['source'], string> = {
  edit: 'Chizish',
  run: 'Tekshirish',
  submit: 'Topshirish',
}

const CHART = { width: 640, height: 180, left: 40, right: 12, top: 12, bottom: 28 }

function percent(value: number | null) {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

function minutes(value: number | null) {
  return value === null ? '—' : `${value} daq.`
}

/** Namunaga yaqinlashish: har bir qadamdagi moslik, tekshirish/topshirish nuqtalari bilan */
function ConvergenceChart({ steps, current, onSelect }: { steps: ErProcessStep[]; current: number; onSelect: (index: number) => void }) {
  const plotWidth = CHART.width - CHART.left - CHART.right
  const plotHeight = CHART.height - CHART.top - CHART.bottom
  const last = Math.max(steps[steps.length - 1].minutes, 1)
  const x = (value: number) => CHART.left + (value / last) * plotWidth
  const y = (value: number) => CHART.top + plotHeight - value * plotHeight
  const path = steps
    .map((step, index) => `${index ? 'L' : 'M'}${x(step.minutes)},${y(step.ratio ?? 0)}`)
    .join('')
  const active = steps[current]

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${CHART.width} ${CHART.height}`}
        className="w-full min-w-[30rem]"
        role="img"
        aria-label="Namunaga moslik vaqt bo'yicha"
      >
        {[0, 0.5, 1].map((tick) => (
          <g key={tick} className="text-muted-foreground">
            <line x1={CHART.left} x2={CHART.left + plotWidth} y1={y(tick)} y2={y(tick)} stroke="currentColor" strokeOpacity={0.15} />
            <text x={CHART.left - 6} y={y(tick)} dy="0.32em" textAnchor="end" fontSize={11} fill="currentColor">
              {tick * 100}%
            </text>
          </g>
        ))}
        <text x={CHART.left} y={CHART.height - 8} fontSize={11} className="fill-muted-foreground">
          0 daq.
        </text>
        <text x={CHART.left + plotWidth} y={CHART.height - 8} textAnchor="end" fontSize={11} className="fill-muted-foreground">
          {steps[steps.length - 1].minutes} daq.
        </text>
        <line
          x1={x(active.minutes)}
          x2={x(active.minutes)}
          y1={CHART.top}
          y2={CHART.top + plotHeight}
          className="stroke-muted-foreground"
          strokeOpacity={0.5}
        />
        <path d={path} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" />
        {steps.map((step, index) =>
          step.source === 'edit' && index !== current ? null : (
            <circle
              key={index}
              cx={x(step.minutes)}
              cy={y(step.ratio ?? 0)}
              r={index === current ? 5 : 4}
              fill={step.source === 'edit' ? 'var(--series-1)' : 'var(--series-2)'}
              stroke="var(--card)"
              strokeWidth={2}
              className="cursor-pointer"
              onClick={() => onSelect(index)}
            >
              <title>
                {SOURCE_LABELS[step.source]}: {percent(step.ratio)}
              </title>
            </circle>
          ),
        )}
      </svg>
    </div>
  )
}

function MetricList({ metrics, strategy }: { metrics: ErProcessMetrics; strategy: string | null }) {
  const items = [
    ['Faol vaqt', minutes(metrics.active_minutes)],
    ['Sessiyalar', String(metrics.sessions)],
    ['Tekshiruvlar', String(metrics.checks)],
    ["Birinchi bog'lanishgacha", minutes(metrics.first_relationship_minutes)],
    ["Qo'shilgan / o'chirilgan", `${metrics.added} / ${metrics.removed}`],
    ['Kardinallikni o\'zgartirish', String(metrics.cardinality_changes)],
    ['Birinchi tekshiruvda moslik', percent(metrics.first_check_ratio)],
    ['Yakuniy moslik', percent(metrics.final_ratio)],
  ]
  return (
    <div className="grid gap-2">
      <div className="text-sm">
        <span className="text-muted-foreground">Strategiya: </span>
        <span className="font-medium">{strategy}</span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
        {items.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="font-medium tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

/** O'qituvchi uchun: talabaning ER-diagrammani qanday chizganini qadamma-qadam qayta ko'rish */
export function ErProcessView({ labId, studentId }: { labId: number; studentId: number }) {
  const process = useQuery({
    queryKey: ['lab-process', labId, studentId],
    queryFn: () => api<ErProcess>(`/labs/${labId}/process/?student=${studentId}`),
  })
  const [selected, setSelected] = useState<number | null>(null)

  if (process.isPending) return <ListSkeleton rows={3} />
  if (process.isError) return <ErrorState error={process.error} onRetry={() => void process.refetch()} />
  const { steps, metrics, strategy_label: strategy } = process.data
  if (!steps.length || !metrics) {
    return (
      <EmptyState
        icon={History}
        title="Chizish jarayoni yozilmagan"
        description="Talaba bu laboratoriyada hali diagramma chizmagan yoki jarayonni yozish joriy etilishidan oldin ishlagan."
      />
    )
  }
  const current = selected ?? steps.length - 1
  const step = steps[current]

  return (
    <div className="grid gap-4">
      <MetricList metrics={metrics} strategy={strategy} />
      <ConvergenceChart steps={steps} current={current} onSelect={setSelected} />
      <div className="grid gap-2">
        <label htmlFor="process-step" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium">
            Qadam {current + 1} / {steps.length}
          </span>
          <Badge variant={step.source === 'edit' ? 'secondary' : 'default'}>{SOURCE_LABELS[step.source]}</Badge>
          <span className="text-muted-foreground">
            {formatDateTime(step.at)} · {step.minutes} daq. · sessiya {step.session} · moslik {percent(step.ratio)}
          </span>
        </label>
        <input
          id="process-step"
          type="range"
          min={0}
          max={steps.length - 1}
          value={current}
          onChange={(event) => setSelected(Number(event.target.value))}
          className="w-full accent-primary"
        />
        {step.events.length ? (
          <ul className="grid gap-0.5 text-sm">
            {step.events.map((event, index) => (
              <li key={index}>
                {event.label}
                {event.detail ? <span className="text-muted-foreground">: {event.detail}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Oldingi qadamdan farq yo'q.</p>
        )}
      </div>
      {/* Muharrir holatni faqat ochilganda o'qiydi: har bir qadam uchun qayta yaratiladi */}
      <ErEditor key={current} value={step.diagram} />
    </div>
  )
}
