import { useQuery } from '@tanstack/react-query'
import { BarChart3 } from 'lucide-react'
import { useState } from 'react'

import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { AiEffectBucket, Statistics, StatisticsGroup } from '@/lib/types'

// Diagramma ranglari index.css dagi --series-* tokenlaridan (yorug' va qorong'i mavzu uchun alohida)
const SERIES_1 = 'var(--series-1)'
const SERIES_2 = 'var(--series-2)'

function formatPercent(value: number | null) {
  return value === null ? '—' : `${value}%`
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  )
}

/** Gorizontal ustun: uzunligi qiymatga mutanosib, qiymat yonida yoziladi (rangga tayanmaydi) */
function HorizontalBar({ value, max, color, label }: { value: number; max: number; color: string; label: string }) {
  // Nol qiymat chizilmaydi (aks holda kichik ustun "bor" bo'lib ko'rinadi); kichik musbat qiymat ko'rinadigan qilinadi
  const width = max && value > 0 ? Math.max(2, (value / max) * 100) : 0
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2" title={label}>
      <div className="h-3.5 min-w-0 flex-1">
        <div className="h-full rounded-r" style={{ width: `${width}%`, background: color }} />
      </div>
    </div>
  )
}

function ErrorsCard({ errors }: { errors: Statistics['top_errors'] }) {
  const max = Math.max(0, ...errors.map((item) => item.count))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Eng ko'p uchragan xatolar</CardTitle>
        <CardDescription>
          Noto'g'ri urinishlardagi xato turlari: har bir urinishda har bir tur bir marta sanaladi.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {errors.length ? (
          <ol className="grid gap-2" aria-label="Xato turlari va soni">
            {errors.map((item) => (
              <li key={item.category} className="grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)_3rem] items-center gap-3 text-sm">
                <span className="truncate" title={item.label}>
                  {item.label}
                </span>
                <HorizontalBar value={item.count} max={max} color={SERIES_1} label={`${item.label}: ${item.count} ta`} />
                <span className="text-right tabular-nums">{item.count}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">Hali xato urinishlar yo'q.</p>
        )}
      </CardContent>
    </Card>
  )
}

function LabsCard({ labs }: { labs: Statistics['labs'] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Laboratoriyalar qiyinligi</CardTitle>
        <CardDescription>
          Yechganlar ulushi qancha past va yechish uchun urinishlar qancha ko'p bo'lsa, laboratoriya shuncha qiyin.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {labs.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Laboratoriya</TableHead>
                <TableHead className="w-[30%]">Yechganlar</TableHead>
                <TableHead className="text-right">Yechish uchun o'rtacha urinish</TableHead>
                <TableHead className="text-right">O'rtacha baho</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {labs.map((lab) => (
                <TableRow key={lab.id}>
                  <TableCell className="max-w-72 truncate font-medium" title={lab.title}>
                    {lab.title}
                    {lab.kind === 'er' ? (
                      <Badge variant="outline" className="ml-2">
                        ER
                      </Badge>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <HorizontalBar
                        value={lab.solved_rate ?? 0}
                        max={100}
                        color={SERIES_1}
                        label={`${lab.solved} / ${lab.students} talaba yechgan`}
                      />
                      <span className="w-24 shrink-0 text-right text-xs tabular-nums">
                        {formatPercent(lab.solved_rate)} ({lab.solved}/{lab.students})
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{lab.attempts_to_solve ?? '—'}</TableCell>
                  <TableCell className="text-right tabular-nums">{lab.average_grade ?? '—'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">Bu guruhlarga hali laboratoriya berilmagan.</p>
        )}
      </CardContent>
    </Card>
  )
}

function AiBucket({ title, bucket, color }: { title: string; bucket: AiEffectBucket; color: string }) {
  return (
    <div className="grid gap-2">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span>{title}</span>
        <span className="text-xl font-semibold tabular-nums">{formatPercent(bucket.rate)}</span>
      </div>
      <HorizontalBar value={bucket.rate ?? 0} max={100} color={color} label={`${bucket.solved} / ${bucket.pairs}`} />
      <span className="text-xs text-muted-foreground tabular-nums">
        {bucket.solved} / {bucket.pairs} holatda keyin to'g'ri yechilgan
      </span>
    </div>
  )
}

function AiEffectCard({ effect }: { effect: Statistics['ai_effect'] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>AI maslahatining ta'siri</CardTitle>
        <CardDescription>
          Xato qilgan talaba laboratoriyani keyinroq to'g'ri yechdimi: AI maslahatini olganlar va olmaganlar
          (nazorat guruhi ham shu yerda) taqqoslanadi.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-2">
        <AiBucket title="AI maslahatini olgan" bucket={effect.with_advice} color={SERIES_1} />
        <AiBucket title="Maslahatsiz" bucket={effect.without_advice} color={SERIES_2} />
      </CardContent>
    </Card>
  )
}

function TestBars({ group, max }: { group: StatisticsGroup; max: number }) {
  const bars = [
    { key: 'pre', label: 'Kirish', value: group.pre_test, count: group.pre_count, color: SERIES_1 },
    { key: 'post', label: 'Chiqish', value: group.post_test, count: group.post_count, color: SERIES_2 },
  ]
  return (
    <div className="grid gap-0.5">
      {bars.map((bar) => (
        <div key={bar.key} className="flex items-center gap-2">
          <span className="w-14 shrink-0 text-xs text-muted-foreground">{bar.label}</span>
          {bar.value === null ? (
            <span className="text-xs text-muted-foreground">hali topshirilmagan</span>
          ) : (
            <>
              <HorizontalBar value={bar.value} max={max} color={bar.color} label={`${bar.label} testi: ${bar.value}% (${bar.count} ta talaba)`} />
              <span className="w-12 shrink-0 text-right text-xs tabular-nums">{bar.value}%</span>
            </>
          )}
        </div>
      ))}
    </div>
  )
}

function GroupsCard({ groups }: { groups: StatisticsGroup[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Guruhlar taqqoslashi</CardTitle>
        <CardDescription>
          Kirish va chiqish testlarining o'rtacha natijasi (%) va o'sish. Tajriba guruhida AI yoqilgan, nazorat guruhida
          o'chirilgan.
        </CardDescription>
        <ul className="flex flex-wrap gap-4 pt-1 text-xs text-muted-foreground" aria-label="Belgilar">
          <li className="flex items-center gap-1.5">
            <span className="size-3 rounded-sm" style={{ background: SERIES_1 }} aria-hidden="true" /> Kirish testi
          </li>
          <li className="flex items-center gap-1.5">
            <span className="size-3 rounded-sm" style={{ background: SERIES_2 }} aria-hidden="true" /> Chiqish testi
          </li>
        </ul>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Guruh</TableHead>
              <TableHead className="w-[34%]">Testlar (o'rtacha %)</TableHead>
              <TableHead className="text-right">O'sish</TableHead>
              <TableHead className="text-right">Laboratoriyalarni yechgan</TableHead>
              <TableHead className="text-right">O'rtacha baho</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.map((group) => (
              <TableRow key={group.id}>
                <TableCell>
                  <div className="font-medium">{group.name}</div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    {group.ai_enabled ? (
                      <Badge variant="outline">AI yoqilgan</Badge>
                    ) : (
                      <Badge className="bg-amber-100 text-amber-800">AI o'chirilgan</Badge>
                    )}
                    {group.students} talaba
                  </div>
                </TableCell>
                <TableCell>
                  <TestBars group={group} max={100} />
                </TableCell>
                <TableCell className="text-right font-medium tabular-nums">
                  {group.gain === null ? '—' : `${group.gain > 0 ? '+' : ''}${group.gain}`}
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatPercent(group.solved_rate)}</TableCell>
                <TableCell className="text-right tabular-nums">{group.average_grade ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function StatisticsPage() {
  const [groupId, setGroupId] = useState('')
  const statistics = useQuery({
    queryKey: ['statistics', groupId],
    queryFn: () => api<Statistics>(`/statistics/${groupId ? `?group=${groupId}` : ''}`),
    placeholderData: (previous) => previous,
  })

  let content
  if (statistics.isPending) {
    content = <ListSkeleton />
  } else if (statistics.isError) {
    content = <ErrorState error={statistics.error} onRetry={() => void statistics.refetch()} />
  } else if (!statistics.data.groups.length) {
    content = (
      <EmptyState icon={BarChart3} title="Hali guruh yo'q" description="Statistika guruhlaringiz talabalari bo'yicha hisoblanadi." />
    )
  } else {
    const data = statistics.data
    content = (
      <div className="grid gap-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile label="Talabalar" value={String(data.overview.students)} />
          <StatTile label="Laboratoriya urinishlari" value={String(data.overview.attempts)} hint={`${data.overview.labs} ta laboratoriya`} />
          <StatTile label="Yechilgan laboratoriyalar" value={formatPercent(data.overview.solved_rate)} hint="talaba va laboratoriya juftliklaridan" />
          <StatTile label="O'rtacha baho" value={data.overview.average_grade === null ? '—' : String(data.overview.average_grade)} hint="100 ballik" />
        </div>
        <GroupsCard groups={data.groups} />
        <div className="grid items-start gap-4 xl:grid-cols-2">
          <ErrorsCard errors={data.top_errors} />
          <AiEffectCard effect={data.ai_effect} />
        </div>
        <LabsCard labs={data.labs} />
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Statistika"
        description="Tajriba natijalari: guruhlar, xatolar, laboratoriyalar qiyinligi va AI ta'siri. To'liq ma'lumot — Virtual laboratoriya sahifasidagi «Tadqiqot ma'lumotlari»."
        actions={
          statistics.data?.groups_available.length ? (
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Guruh</span>
              <select
                className="h-10 rounded-md border bg-background px-2"
                value={groupId}
                onChange={(event) => setGroupId(event.target.value)}
              >
                <option value="">Barcha guruhlar</option>
                {statistics.data.groups_available.map((group) => (
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
