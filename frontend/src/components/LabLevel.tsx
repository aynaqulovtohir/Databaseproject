import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { localized, t } from '@/lib/i18n'

// eslint-disable-next-line react/only-export-components
export const LEVEL_LABELS = localized(['Juda sodda', 'Sodda', "O'rtacha", 'Murakkab', 'Juda murakkab'])

/** O'qituvchi belgilagan murakkablik (1-5): to'ldirilgan nuqtalar soni = daraja, yonida nomi (rangga tayanmaydi) */
export function LabLevelBadge({ level }: { level: number }) {
  return (
    <Badge variant="outline" title={t('Murakkablik: {level} / 5', { level })} aria-label={t('Murakkablik {level} / 5 — {value}', { level, value: LEVEL_LABELS[level - 1] })}>
      <span className="flex gap-0.5" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((step) => (
          <span key={step} className={cn('size-1.5 rounded-full', step <= level ? 'bg-current' : 'bg-muted-foreground/25')} />
        ))}
      </span>
      {LEVEL_LABELS[level - 1]}
    </Badge>
  )
}
