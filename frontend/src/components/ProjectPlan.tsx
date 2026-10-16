import type { Grade, RubricCriterion } from '@/lib/types'

/** Rubrika mezonlari ro'yxati: nomi, bali va nima tekshirilishi. */
export function RubricList({ criteria, title = 'Baholash rubrikasi' }: { criteria: RubricCriterion[]; title?: string }) {
  if (!criteria.length) return null
  const total = criteria.reduce((sum, item) => sum + item.points, 0)
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        <span className="text-xs text-muted-foreground tabular-nums">jami {total} ball</span>
      </div>
      <ul className="grid gap-1.5 text-sm">
        {criteria.map((item, index) => (
          <li key={index} className="flex items-baseline justify-between gap-3">
            <span className="min-w-0">
              <span className="font-medium">{item.name}</span>
              {item.description ? <span className="text-muted-foreground"> — {item.description}</span> : null}
            </span>
            <span className="shrink-0 tabular-nums">{item.points}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Baho mezonlar bo'yicha qanday tarkib topgani. */
export function GradeBreakdown({ grade }: { grade: Grade }) {
  if (!grade.rubric_scores?.length) return null
  return (
    <ul className="mt-2 grid gap-1 text-sm">
      {grade.rubric_scores.map((item, index) => (
        <li key={index} className="flex items-baseline justify-between gap-3">
          <span className="min-w-0">{item.name}</span>
          <span className="shrink-0 tabular-nums">
            {item.score} / {item.points}
          </span>
        </li>
      ))}
    </ul>
  )
}
