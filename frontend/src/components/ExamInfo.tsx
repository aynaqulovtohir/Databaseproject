import { Clock } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { formatDateTime } from '@/lib/format'
import type { LabExamInfo } from '@/lib/types'
import { localized, t } from '@/lib/i18n'

const STATE_LABELS: Record<LabExamInfo['state'], string> = localized({
  upcoming: 'Imtihon kutilmoqda',
  active: 'Imtihon davom etmoqda',
  finished: 'Imtihon tugagan',
})

/** Modul sarlavhasi yonida: imtihon holati va vaqti */
export function ExamBadge({ exam }: { exam: LabExamInfo }) {
  return (
    <Badge variant={exam.state === 'active' ? 'destructive' : 'outline'}>
      <Clock aria-hidden="true" />
      {STATE_LABELS[exam.state]}: {formatDateTime(exam.starts_at)} — {formatDateTime(exam.ends_at)}
    </Badge>
  )
}

/** Laboratoriya sahifasida talabaga: imtihon qoidalari */
export function ExamBanner({ exam }: { exam: LabExamInfo }) {
  const text =
    exam.state === 'active'
      ? t(
          "Imtihon {time} da tugaydi. Imtihon davomida AI yordami, murabbiy va o'zaro baholash o'chirilgan; ball avtomatik qo'yiladi, tuzatilgan diagramma imtihon tugagach ko'rsatiladi.",
          { time: formatDateTime(exam.ends_at) },
        )
      : exam.state === 'finished'
        ? t("Imtihon {time} da tugagan: yechimni ko'rishingiz mumkin, lekin endi tekshirib yoki topshirib bo'lmaydi.", {
            time: formatDateTime(exam.ends_at),
          })
        : t('Imtihon {time} da boshlanadi.', { time: formatDateTime(exam.starts_at) })
  return (
    <div
      className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"
      role="status"
    >
      <Clock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div>
        <div className="font-medium">{STATE_LABELS[exam.state]}</div>
        <p>{text}</p>
      </div>
    </div>
  )
}
