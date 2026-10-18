import { useQuery } from '@tanstack/react-query'
import { Info } from 'lucide-react'

import { ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { LabAnalysis, LabAnalysisRow } from '@/lib/types'
import { cn } from '@/lib/utils'

/** Qiyinlik darajasi: 5 bo'lakli shkala (to'ldirilgan bo'laklar soni = daraja), rangga tayanmaydi */
function LevelMeter({ level }: { level: number }) {
  return (
    <span className="flex gap-0.5" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((step) => (
        <span
          key={step}
          className={cn('h-2.5 w-2 rounded-sm', step <= level ? 'bg-[var(--series-2)]' : 'bg-muted')}
        />
      ))}
    </span>
  )
}

function format(value: number | null, digits = 2) {
  return value === null ? '—' : value.toFixed(digits)
}

const VERDICT_VARIANT = { good: 'secondary', review: 'outline', replace: 'destructive' } as const

function LabRow({ row }: { row: LabAnalysisRow }) {
  if (!row.analysed || !row.level) {
    return (
      <TableRow>
        <TableCell className="max-w-72 whitespace-normal font-medium">{row.title}</TableCell>
        <TableCell colSpan={6} className="text-sm text-muted-foreground">
          Ma'lumot kam: {row.started} ta talaba boshlagan
        </TableCell>
      </TableRow>
    )
  }
  return (
    <TableRow className="align-top">
      <TableCell className="max-w-72 whitespace-normal">
        <div className="font-medium">{row.title}</div>
        {row.advice.length ? (
          <ul className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
            {row.advice.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        ) : null}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2" aria-label={`Daraja ${row.level.number} — ${row.level.label}`}>
          <LevelMeter level={row.level.number} />
          <span className="text-sm whitespace-nowrap">
            {row.level.number} · {row.level.label}
          </span>
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground tabular-nums">
          p = {format(row.p)} · {row.started} talaba
        </div>
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {format(row.r)}
        {row.discrimination ? <span className="block text-xs text-muted-foreground">{row.discrimination.label}</span> : null}
      </TableCell>
      <TableCell className="text-right tabular-nums">{format(row.d)}</TableCell>
      <TableCell className="text-right tabular-nums">{format(row.alpha_if_deleted, 3)}</TableCell>
      <TableCell className="text-right text-sm tabular-nums whitespace-nowrap">
        {format(row.cohorts?.ai.p ?? null)} / {format(row.cohorts?.control.p ?? null)}
      </TableCell>
      <TableCell>
        {row.verdict ? <Badge variant={VERDICT_VARIANT[row.verdict.key]}>{row.verdict.label}</Badge> : null}
      </TableCell>
    </TableRow>
  )
}

/** Laboratoriyalarning psixometrik tahlili: qiyinlik 5 darajada, ajrata olish va Cronbach α */
export function LabAnalysisCard({ groupId }: { groupId: string }) {
  const analysis = useQuery({
    queryKey: ['labs-analysis', groupId],
    queryFn: () => api<LabAnalysis>(`/statistics/labs-analysis/${groupId ? `?group=${groupId}` : ''}`),
    placeholderData: (previous) => previous,
  })

  let content
  if (analysis.isPending) content = <ListSkeleton rows={3} />
  else if (analysis.isError) content = <ErrorState error={analysis.error} onRetry={() => void analysis.refetch()} />
  else {
    const data = analysis.data
    const { reliability } = data
    content = (
      <div className="grid gap-4">
        {data.consent_required ? (
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              Tahlilga tadqiqotga rozi bo'lgan {data.students} ta talaba kirdi
              {data.excluded_no_consent ? ` (${data.excluded_no_consent} tasi rozilik bermagan yoki hali qaror qilmagan)` : ''}.
            </span>
          </p>
        ) : null}

        <div className="grid gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="grid grid-cols-5 gap-2" aria-label="Laboratoriyalar darajalar bo'yicha">
            {data.distribution.map((item) => (
              <div key={item.key} className="rounded-xl border bg-card p-3">
                <LevelMeter level={item.number} />
                <div className="mt-2 text-2xl font-semibold tabular-nums">{item.count}</div>
                <div className="text-xs text-muted-foreground">
                  {item.number}. {item.label}
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-xl border bg-card p-3">
            <div className="text-sm text-muted-foreground">Ishonchlilik (Cronbach α)</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-semibold tabular-nums">{format(reliability.alpha, 3)}</span>
              {reliability.interpretation ? <Badge variant="outline">{reliability.interpretation.label}</Badge> : null}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {reliability.alpha === null
                ? `Hisoblash uchun kamida 2 ta umumiy laboratoriya va ularning hammasini boshlagan ${data.min_students} ta talaba kerak.`
                : `${reliability.labs} ta laboratoriya, ${reliability.students} ta talaba · o'rtacha ${format(reliability.mean, 1)}, SD ${format(reliability.sd, 1)}, SEM ${format(reliability.sem, 1)} (100 ballik)`}
            </div>
            {reliability.alpha !== null && reliability.students < data.reliable_students ? (
              <div className="mt-1 text-xs text-muted-foreground">
                {data.reliable_students} tadan kam talaba: natija dastlabki.
              </div>
            ) : null}
          </div>
        </div>

        {data.labs.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Laboratoriya</TableHead>
                <TableHead>Qiyinlik darajasi</TableHead>
                <TableHead className="text-right" title="Tuzatilgan korrelyatsiya: laboratoriya bali va boshqa laboratoriyalardagi o'rtacha bal">
                  Ajratish r
                </TableHead>
                <TableHead className="text-right" title="Yuqori va quyi 27% talabalar farqi">
                  D
                </TableHead>
                <TableHead className="text-right" title="Shu laboratoriyasiz Cronbach α">
                  α olib tashlansa
                </TableHead>
                <TableHead className="text-right">p: AI / nazorat</TableHead>
                <TableHead>Xulosa</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.labs.map((row) => (
                <LabRow key={row.id} row={row} />
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">Bu guruhlarga hali laboratoriya berilmagan.</p>
        )}
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Laboratoriyalar psixometrikasi</CardTitle>
        <CardDescription>
          Har bir laboratoriya test savoli kabi tahlil qilinadi. Qiyinlik p — boshlagan talabalar o'rtacha bahosining
          ulushi: 1 juda oson (p &gt; 0.80), 2 oson, 3 o'rtacha, 4 qiyin, 5 juda qiyin (p ≤ 0.20). Ajratish r ≥ 0.30
          yaxshi, 0.20 dan past — laboratoriya kuchli va kuchsiz talabalarni farqlamaydi. Natija tadqiqot eksportida ham
          bor (laboratoriyalar_tahlili.csv).
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
