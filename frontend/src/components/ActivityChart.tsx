// Kunlik faollik grafigi (NiceAdmin "Reports" kartasi o'rnida). Kutubxonasiz SVG: 2px chiziqlar, kursor ostida
// vertikal chiziq va qiymatlar, har doim izoh (legend) va jadval ko'rinishi — rang yagona belgi bo'lmasin.
import { useLayoutEffect, useRef, useState, type PointerEvent } from 'react'

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { Dashboard } from '@/lib/types'

const SERIES = [
  { key: 'submissions', label: 'Topshiriq yechimlari', color: 'var(--series-1)' },
  { key: 'lab_attempts', label: 'Laboratoriya urinishlari', color: 'var(--series-2)' },
  { key: 'quiz_attempts', label: 'Test topshirishlari', color: 'var(--series-3)' },
] as const

const HEIGHT = 260
const PAD = { top: 12, right: 12, bottom: 28, left: 32 }

function dayLabel(iso: string) {
  const [, month, day] = iso.split('-')
  return `${day}.${month}`
}

function niceMax(value: number) {
  if (value <= 4) return 4
  const step = Math.pow(10, Math.floor(Math.log10(value)))
  return Math.ceil(value / step) * step
}

export function ActivityChart({ chart, showTable }: { chart: Dashboard['chart']; showTable: boolean }) {
  const boxRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)
  const [hover, setHover] = useState<number | null>(null)

  useLayoutEffect(() => {
    const box = boxRef.current
    if (!box) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    observer.observe(box)
    return () => observer.disconnect()
  }, [])

  const days = chart.days
  const max = niceMax(Math.max(1, ...SERIES.flatMap((s) => chart.series[s.key])))
  const innerW = width - PAD.left - PAD.right
  const innerH = HEIGHT - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (days.length > 1 ? (i / (days.length - 1)) * innerW : innerW / 2)
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max]
  const labelEvery = width < 480 ? 3 : 2

  function onMove(event: PointerEvent<SVGRectElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = (event.clientX - rect.left) / rect.width
    setHover(Math.round(Math.min(1, Math.max(0, ratio)) * (days.length - 1)))
  }

  const total = SERIES.reduce((sum, s) => sum + chart.series[s.key].reduce((a, b) => a + b, 0), 0)

  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Izoh">
        {SERIES.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ background: s.color }} aria-hidden="true" />
            {s.label}
          </li>
        ))}
      </ul>

      {showTable ? (
        <div className="max-h-[260px] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Kun</TableHead>
                {SERIES.map((s) => (
                  <TableHead key={s.key} className="text-right">
                    {s.label}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {days.map((day, i) => (
                <TableRow key={day}>
                  <TableCell>{dayLabel(day)}</TableCell>
                  {SERIES.map((s) => (
                    <TableCell key={s.key} className="text-right tabular-nums">
                      {chart.series[s.key][i]}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div ref={boxRef} className="relative">
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label={`So'nggi ${days.length} kunlik faollik grafigi, jami ${total} ta harakat. Aniq sonlar jadval ko'rinishida.`}
            className="block max-w-full"
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(tick)} y2={y(tick)} stroke="var(--border)" />
                <text x={PAD.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-muted-foreground text-[11px]">
                  {Number.isInteger(tick) ? tick : ''}
                </text>
              </g>
            ))}
            {days.map((day, i) =>
              i % labelEvery === (days.length - 1) % labelEvery ? (
                <text key={day} x={x(i)} y={HEIGHT - 8} textAnchor="middle" className="fill-muted-foreground text-[11px]">
                  {dayLabel(day)}
                </text>
              ) : null,
            )}
            {SERIES.map((s) => (
              <polyline
                key={s.key}
                fill="none"
                stroke={s.color}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
                points={chart.series[s.key].map((v, i) => `${x(i)},${y(v)}`).join(' ')}
              />
            ))}
            {hover !== null ? (
              <g>
                <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--muted-foreground)" strokeDasharray="3 3" />
                {SERIES.map((s) => (
                  <circle key={s.key} cx={x(hover)} cy={y(chart.series[s.key][hover])} r={4} fill={s.color} stroke="var(--card)" strokeWidth={2} />
                ))}
              </g>
            ) : null}
            <rect
              x={PAD.left}
              y={PAD.top}
              width={innerW}
              height={innerH}
              fill="transparent"
              onPointerMove={onMove}
              onPointerDown={onMove}
              onPointerLeave={() => setHover(null)}
            />
          </svg>
          {hover !== null ? (
            <div
              className="pointer-events-none absolute top-2 z-10 min-w-44 rounded-md bg-popover px-3 py-2 text-xs shadow-(--card-shadow) ring-1 ring-border"
              style={x(hover) > width / 2 ? { right: width - x(hover) + 12 } : { left: x(hover) + 12 }}
            >
              <div className="mb-1 font-semibold text-heading">{dayLabel(days[hover])}</div>
              {SERIES.map((s) => (
                <div key={s.key} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-1.5 text-muted-foreground">
                    <span className="size-2 rounded-full" style={{ background: s.color }} aria-hidden="true" />
                    {s.label}
                  </span>
                  <span className="font-semibold text-foreground tabular-nums">{chart.series[s.key][hover]}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
