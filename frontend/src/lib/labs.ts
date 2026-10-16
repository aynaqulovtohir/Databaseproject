import type { Lab } from '@/lib/types'

/** Namunaviy yechimi bor oddiy SQL laboratoriyasi uchun AI yaratadi (backend ham shuni tekshiradi) */
export function supportsGeneration(lab: Lab) {
  return (
    lab.kind === 'sql' &&
    Boolean(lab.solution_sql?.trim()) &&
    !lab.plan_query?.trim() &&
    !lab.concurrent &&
    !lab.given_diagram?.entities.length
  )
}
