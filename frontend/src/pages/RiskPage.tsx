import { useQuery } from '@tanstack/react-query'
import { CircleAlert, CircleCheck, ShieldAlert, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { useGroupOptions } from '@/lib/groups'
import type { RiskLevel, RiskReport } from '@/lib/types'
import { t } from '@/lib/i18n'

/** Daraja belgisi: ikonka + matn (faqat rangga tayanmaydi) */
function LevelBadge({ level, label }: { level: RiskLevel; label: string }) {
  if (level === 'high') {
    return (
      <Badge variant="destructive">
        <TriangleAlert aria-hidden="true" />
        {label}
      </Badge>
    )
  }
  if (level === 'medium') {
    return (
      <Badge variant="secondary">
        <CircleAlert aria-hidden="true" />
        {label}
      </Badge>
    )
  }
  if (level === 'low') return <Badge variant="outline">{label}</Badge>
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <CircleCheck className="size-3.5" aria-hidden="true" />
      {label}
    </span>
  )
}

export function RiskPage() {
  const { groups, isPending } = useGroupOptions()
  const [chosen, setChosen] = useState('')
  const groupId = chosen || String(groups[0]?.id ?? '')
  const report = useQuery({
    queryKey: ['risk', groupId],
    queryFn: () => api<RiskReport>(`/risk/?group=${groupId}`),
    enabled: Boolean(groupId),
    placeholderData: (previous) => previous,
  })

  let content
  if (isPending || (groupId && report.isPending)) {
    content = <ListSkeleton />
  } else if (!groups.length) {
    content = <EmptyState icon={ShieldAlert} title={t("Hali guruh yo'q")} description={t("Erta ogohlantirish o'zingiz o'qitadigan guruhlar bo'yicha hisoblanadi.")} />
  } else if (report.isError) {
    content = <ErrorState error={report.error} onRetry={() => void report.refetch()} />
  } else if (report.data) {
    const data = report.data
    const counts = { high: 0, medium: 0, low: 0, none: 0 }
    data.students.forEach((student) => (counts[student.level] += 1))
    content = (
      <Card>
        <CardHeader>
          <CardTitle>{data.group.name}</CardTitle>
          <CardDescription>
            {t("Yuqori xavf: {high} · O'rta: {medium} · Past: {low} · Xavf yo'q: {none}. Guruhda {labs} ta laboratoriya, yechilganlar medianasi — {median_solved}.", {
              high: counts.high,
              medium: counts.medium,
              low: counts.low,
              none: counts.none,
              labs: data.labs,
              median_solved: data.median_solved,
            })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.students.length ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('Talaba')}</TableHead>
                    <TableHead>{t('Xavf')}</TableHead>
                    <TableHead>{t('Sabablar')}</TableHead>
                    <TableHead>{t('Yechgan')}</TableHead>
                    <TableHead>{t('Oxirgi faollik')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.students.map((student) => (
                    <TableRow key={student.id}>
                      <TableCell className="font-medium">{student.name}</TableCell>
                      <TableCell>
                        <LevelBadge level={student.level} label={student.level_label} />
                      </TableCell>
                      <TableCell className="max-w-md whitespace-normal">
                        {student.reasons.length ? (
                          <ul className="grid list-disc gap-0.5 pl-4 text-sm">
                            {student.reasons.map((reason) => (
                              <li key={reason.code}>{reason.text}</li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="tabular-nums">{student.solved}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {student.last_activity ? formatDateTime(student.last_activity) : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{t("Guruhda talaba yo'q.")}</p>
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      <PageHeader
        title={t('Erta ogohlantirish')}
        description={t("E'tibor kerak bo'lgan talabalar: uzoq vaqt faol emas, guruhdan orqada, bir laboratoriyada qolib ketgan, past o'zlashtirish yoki test natijasi, AI maslahatlariga haddan tashqari tayanish. Bu baho emas — qaror o'qituvchida. Telegram'ni bog'lagan o'qituvchiga haftasiga bir marta yuqori xavfli talabalar ro'yxati yuboriladi.")}
        actions={
          groups.length > 1 ? (
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">{t('Guruh')}</span>
              <select className="h-10 rounded-md border bg-background px-2" value={groupId} onChange={(event) => setChosen(event.target.value)}>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null
        }
      />
      {content}
    </>
  )
}
