import { useId } from 'react'

import { CONFIDENCE_LEVELS } from '@/lib/confidence'
import { cn } from '@/lib/utils'

/** «Javobingizga qanchalik ishonasiz?» — 1-5 shkala (ixtiyoriy), va oldingi tekshiruvdan keyingi izoh */
export function ConfidencePicker({
  value,
  onChange,
  note,
}: {
  value: number | null
  onChange: (value: number | null) => void
  note: string | null
}) {
  const labelId = useId()
  return (
    <div className="grid gap-1.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span id={labelId} className="text-sm">
          Javobingizga qanchalik ishonasiz?
        </span>
        <div role="group" aria-labelledby={labelId} className="inline-flex rounded-lg border p-0.5">
          {CONFIDENCE_LEVELS.map((level) => (
            <button
              key={level}
              type="button"
              aria-pressed={value === level}
              aria-label={`${level} — ${level === 1 ? 'umuman ishonmayman' : level === 5 ? "to'liq ishonaman" : `5 dan ${level}`}`}
              className={cn(
                'size-8 rounded-md text-sm tabular-nums transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                value === level ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
              )}
              // Qayta bosilsa, tanlov bekor qilinadi (belgilash ixtiyoriy)
              onClick={() => onChange(value === level ? null : level)}
            >
              {level}
            </button>
          ))}
        </div>
        <span className="text-xs text-muted-foreground">1 — umuman ishonmayman, 5 — to'liq ishonaman (ixtiyoriy)</span>
      </div>
      {note ? (
        <p className="text-sm text-muted-foreground" role="status">
          {note}
        </p>
      ) : null}
    </div>
  )
}
