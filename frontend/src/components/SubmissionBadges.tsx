import { Badge } from '@/components/ui/badge'
import { isPast } from '@/lib/format'
import type { Submission, SubmissionStatus } from '@/lib/types'
import { localized, t } from '@/lib/i18n'

const STATUS_LABELS: Record<SubmissionStatus, string> = localized({
  submitted: 'Tekshirilmoqda',
  graded: 'Baholangan',
  returned: 'Qaytarilgan',
})

const STATUS_CLASSES: Record<SubmissionStatus, string> = {
  submitted: 'bg-sky-100 text-sky-800',
  graded: 'bg-emerald-100 text-emerald-800',
  returned: 'bg-amber-100 text-amber-800',
}

export function SubmissionStatusBadge({ submission }: { submission: Pick<Submission, 'status' | 'is_late'> }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Badge className={STATUS_CLASSES[submission.status]}>{STATUS_LABELS[submission.status]}</Badge>
      {submission.is_late ? <Badge variant="destructive">{t('Kechikkan')}</Badge> : null}
    </span>
  )
}

export function DeadlineBadge({ deadline }: { deadline: string }) {
  return isPast(deadline) ? (
    <Badge variant="destructive">{t("Muddat o'tgan")}</Badge>
  ) : (
    <Badge variant="secondary">{t('Ochiq')}</Badge>
  )
}
