import { formatDateTime } from '@/lib/format'
import type { Quiz } from '@/lib/types'
import { t } from '@/lib/i18n'

/** Test vaqti haqida qisqa matn: "20.10.2026 09:00 — 20.10.2026 10:00 · 30 daqiqa" */
export function quizTiming(quiz: Quiz) {
  const parts = []
  if (quiz.opens_at || quiz.closes_at) {
    parts.push(`${quiz.opens_at ? formatDateTime(quiz.opens_at) : '…'} — ${quiz.closes_at ? formatDateTime(quiz.closes_at) : '…'}`)
  }
  parts.push(
    quiz.time_limit_minutes ? t('{minutes} daqiqa', { minutes: quiz.time_limit_minutes }) : t('vaqt cheklanmagan'),
  )
  parts.push(t('{count} ta savol', { count: quiz.question_count }))
  return parts.join(' · ')
}
