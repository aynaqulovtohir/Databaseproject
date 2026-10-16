import { useQuery } from '@tanstack/react-query'
import { Gauge, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { CompetenceStatisticsCard } from '@/components/CompetenceStatistics'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type {
  CompetenceComparison,
  CompetenceComponent,
  CompetenceDistribution,
  CompetenceLevel,
  CompetenceModel,
  CompetenceReport,
  CompetenceScore,
  CompetenceStage,
  CompetenceSummary,
} from '@/lib/types'

// Darajalar tartibli: bitta ko'k tusning pog'onalari (index.css dagi --level-* tokenlari, ikkala mavzu uchun tekshirilgan)
const LEVEL_ORDER: CompetenceLevel[] = ['low', 'medium', 'high']
const LEVEL_COLORS: Record<CompetenceLevel, string> = {
  low: 'var(--level-low)',
  medium: 'var(--level-medium)',
  high: 'var(--level-high)',
}
const STAGE_LABELS: Record<CompetenceStage, string> = {
  initial: 'Tajriba boshida',
  final: 'Tajriba oxirida',
  delayed: 'Tajribadan keyin',
}
const STAGE_ORDER: CompetenceStage[] = ['initial', 'final', 'delayed']

/** Modelda kamida bitta komponent o'lchanadigan kesimlar (kechiktirilgan test bog'lanmagan bo'lsa, u ko'rsatilmaydi) */
function usedStages(components: CompetenceComponent[]) {
  return STAGE_ORDER.filter((stage) => components.some((component) => component.stages.includes(stage)))
}
const COHORT_LABELS = { experimental: 'Tajriba guruhi (AI yoqilgan)', control: 'Nazorat guruhi' } as const

type LevelLabels = Record<CompetenceLevel, string>

function Swatch({ level }: { level: CompetenceLevel }) {
  return <span className="inline-block size-2.5 shrink-0 rounded-sm" style={{ background: LEVEL_COLORS[level] }} aria-hidden="true" />
}

function Legend({ labels }: { labels: LevelLabels }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Darajalar">
      {LEVEL_ORDER.map((level) => (
        <li key={level} className="flex items-center gap-1.5">
          <Swatch level={level} />
          {labels[level]}
        </li>
      ))}
    </ul>
  )
}

/** 100% li ustun: darajalar ulushi. Raqamlar ustun ostida yoziladi (rangga tayanmaydi). */
function LevelBar({ distribution, labels }: { distribution: CompetenceDistribution; labels: LevelLabels }) {
  if (!distribution.measured) {
    return <p className="text-xs text-muted-foreground">O'lchanmagan</p>
  }
  const segments = LEVEL_ORDER.filter((level) => distribution.counts[level] > 0)
  return (
    <div className="grid gap-1">
      <div className="flex h-4 gap-[2px]" role="img" aria-label={LEVEL_ORDER.map((level) => `${labels[level]}: ${distribution.percents[level]}%`).join(', ')}>
        {segments.map((level, index) => (
          <div
            key={level}
            className={index === 0 ? (segments.length === 1 ? 'rounded' : 'rounded-l') : index === segments.length - 1 ? 'rounded-r' : ''}
            style={{ width: `${distribution.percents[level]}%`, background: LEVEL_COLORS[level] }}
            title={`${labels[level]}: ${distribution.counts[level]} talaba (${distribution.percents[level]}%)`}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground tabular-nums">
        {LEVEL_ORDER.map((level) => `${labels[level]} ${distribution.counts[level]} (${distribution.percents[level]}%)`).join(' · ')}
        {distribution.unmeasured ? ` · o'lchanmagan ${distribution.unmeasured}` : ''}
      </p>
    </div>
  )
}

function stageBadges(stages: CompetenceStage[]) {
  return stages.length ? (
    stages.map((stage) => (
      <Badge key={stage} variant="outline">
        {STAGE_LABELS[stage]}
      </Badge>
    ))
  ) : (
    <Badge variant="destructive">O'lchanmaydi</Badge>
  )
}

function ModelCard({ model }: { model: CompetenceModel }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Kompetentlik modeli</CardTitle>
        <CardDescription>
          Komponent bali — ko'rsatkichlarning vaznli o'rtachasi (0–100). Komponentlar, ko'rsatkichlar, vaznlar va daraja
          chegaralari admin panelda («Kompetentlik modeli» bo'limi) o'zgartiriladi.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {model.components.map((component) => (
          <details key={component.id} className="group rounded-lg border p-3">
            <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm font-medium select-none">
              {component.name}
              <span className="font-normal text-muted-foreground">
                · past &lt; {component.medium_from}% ≤ o'rta &lt; {component.high_from}% ≤ yuqori
              </span>
            </summary>
            {component.description ? <p className="mt-2 text-sm text-muted-foreground">{component.description}</p> : null}
            <ul className="mt-3 grid gap-2">
              {component.indicators.map((indicator) => (
                <li key={indicator.id} className="flex flex-wrap items-center gap-2 text-sm">
                  <span>{indicator.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {indicator.source_label}
                    {indicator.topics.length ? ` (${indicator.topics.join(', ')})` : ''} · vazn {indicator.weight}
                  </span>
                  {stageBadges(indicator.stages)}
                  {indicator.ai_only ? <Badge variant="secondary">Faqat AI yoqilgan guruhlarda</Badge> : null}
                </li>
              ))}
              {!component.indicators.length ? <li className="text-sm text-muted-foreground">Ko'rsatkich yo'q</li> : null}
            </ul>
          </details>
        ))}
      </CardContent>
    </Card>
  )
}

/** Kesimlar o'rtasida komponentlar to'plami farq qilsa, umumiy ballni taqqoslab bo'lmaydi. */
function comparabilityWarnings(components: CompetenceComponent[]) {
  const warnings: string[] = []
  const stages = usedStages(components)
  const partial = components.filter((component) => component.stages.length && component.stages.length < stages.length)
  if (partial.length) {
    warnings.push(
      `Umumiy ball kesimlar o'rtasida taqqoslanmaydi: ${partial
        .map((component) => `«${component.name}» faqat ${component.stages.map((stage) => STAGE_LABELS[stage].toLowerCase()).join(' va ')}`)
        .join(', ')} o'lchanadi. Komponentlar bo'yicha solishtiring yoki ikkala kesimga ham o'lchov qo'shing.`,
    )
  }
  const missing = components.filter((component) => !component.stages.length)
  if (missing.length) {
    warnings.push(`Hech qaysi kesimda o'lchanmaydi: ${missing.map((component) => `«${component.name}»`).join(', ')} — testlarni bog'lang.`)
  }
  if (components.some((component) => component.indicators.some((indicator) => indicator.ai_only))) {
    warnings.push("AI baholaydigan ko'rsatkichlar nazorat guruhida o'lchanmaydi: bunday komponentlarda guruhlar boshqa ko'rsatkichlar bo'yicha solishtiriladi.")
  }
  return warnings
}

function summaryRows(model: CompetenceModel, summary: CompetenceSummary) {
  const byId = new Map(summary.components.map((item) => [item.component, item]))
  return [
    ...model.components.map((component) => ({ key: String(component.id), name: component.name, item: byId.get(component.id) })),
    { key: 'overall', name: 'Umumiy', item: summary.overall },
  ]
}

function ComparisonCard({ model, comparison, labels }: { model: CompetenceModel; comparison: CompetenceComparison; labels: LevelLabels }) {
  const cohorts = (['experimental', 'control'] as const).filter((cohort) => comparison.cohorts[cohort].students > 0)
  const warnings = comparabilityWarnings(model.components)
  const stages = usedStages(model.components)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Tajriba va nazorat guruhlari</CardTitle>
        <CardDescription>
          Kompetentlik darajalari taqsimoti har bir kesimda (ulush o'lchangan talabalar ichida). Tajriba guruhi —
          AI yordamchisi yoqilgan guruhlar, nazorat guruhi — o'chirilganlar (Guruhlar sahifasida sozlanadi).
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <Legend labels={labels} />
        {warnings.map((warning) => (
          <Alert key={warning}>
            <TriangleAlert aria-hidden="true" />
            <AlertDescription>{warning}</AlertDescription>
          </Alert>
        ))}
        {comparison.cohorts.control.students === 0 ? (
          <Alert>
            <TriangleAlert aria-hidden="true" />
            <AlertDescription>
              Nazorat guruhi yo'q: solishtirish uchun kamida bitta guruhda AI yordamchisini o'chiring.
            </AlertDescription>
          </Alert>
        ) : null}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-48">Komponent</TableHead>
                <TableHead className="w-36">Kesim</TableHead>
                {cohorts.map((cohort) => (
                  <TableHead key={cohort} className="min-w-72">
                    {COHORT_LABELS[cohort]}
                    <span className="ml-1 font-normal text-muted-foreground">({comparison.cohorts[cohort].students} talaba)</span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {summaryRows(model, comparison.cohorts.experimental.stages.initial).map((row) =>
                stages.map((stage, index) => (
                  <TableRow key={`${row.key}-${stage}`} className={index === 0 ? 'border-t-2' : undefined}>
                    {index === 0 ? (
                      <TableCell rowSpan={stages.length} className="align-top font-medium whitespace-normal">
                        {row.name}
                      </TableCell>
                    ) : null}
                    <TableCell className="align-top text-muted-foreground">{STAGE_LABELS[stage]}</TableCell>
                    {cohorts.map((cohort) => {
                      const summary = comparison.cohorts[cohort].stages[stage]
                      const item =
                        row.key === 'overall'
                          ? summary.overall
                          : summary.components.find((component) => String(component.component) === row.key)
                      return (
                        <TableCell key={cohort} className="align-top whitespace-normal">
                          {item ? (
                            <div className="grid gap-1">
                              <LevelBar distribution={item.distribution} labels={labels} />
                              {item.mean !== null ? (
                                <span className="text-xs text-muted-foreground tabular-nums">O'rtacha ball: {item.mean}</span>
                              ) : null}
                            </div>
                          ) : null}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                )),
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}

function ScoreCell({ value, labels }: { value: CompetenceScore | undefined; labels: LevelLabels }) {
  if (!value || value.score === null || !value.level) {
    return <span className="text-muted-foreground">—</span>
  }
  return (
    <span className="inline-flex items-center gap-1.5 tabular-nums">
      <Swatch level={value.level} />
      {value.score}
      <span className="text-xs text-muted-foreground">{labels[value.level].toLowerCase()}</span>
    </span>
  )
}

function GroupCard({ model, comparison, labels }: { model: CompetenceModel; comparison: CompetenceComparison; labels: LevelLabels }) {
  const [groupId, setGroupId] = useState(String(comparison.groups[0]?.id ?? ''))
  const [stage, setStage] = useState<CompetenceStage>('final')
  const report = useQuery({
    queryKey: ['competence-report', groupId, stage],
    queryFn: () => api<CompetenceReport>(`/competence/report/?group=${groupId}&stage=${stage}`),
    enabled: Boolean(groupId),
    placeholderData: (previous) => previous,
  })

  let content
  if (report.isPending) {
    content = <ListSkeleton />
  } else if (report.isError) {
    content = <ErrorState error={report.error} onRetry={() => void report.refetch()} />
  } else if (!report.data.students.length) {
    content = <p className="text-sm text-muted-foreground">Guruhda talaba yo'q.</p>
  } else {
    content = (
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Talaba</TableHead>
              {model.components.map((component) => (
                <TableHead key={component.id}>{component.name}</TableHead>
              ))}
              <TableHead>Umumiy</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.data.students.map((student) => (
              <TableRow key={student.id}>
                <TableCell className="font-medium">{student.name}</TableCell>
                {model.components.map((component) => (
                  <TableCell key={component.id}>
                    <ScoreCell value={student.components[String(component.id)]} labels={labels} />
                  </TableCell>
                ))}
                <TableCell>
                  <ScoreCell value={student.overall} labels={labels} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Guruh talabalari</CardTitle>
        <CardDescription>Har bir talabaning komponentlar bo'yicha bali (0–100) va darajasi. «—» — bu kesimda o'lchanmagan.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Guruh</span>
            <select className="h-10 rounded-md border bg-background px-2" value={groupId} onChange={(event) => setGroupId(event.target.value)}>
              {comparison.groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                  {group.ai_enabled ? '' : ' (nazorat)'}
                </option>
              ))}
            </select>
          </label>
          <div className="inline-flex rounded-lg border p-0.5" role="group" aria-label="Kesim">
            {usedStages(model.components).map((item) => (
              <Button
                key={item}
                type="button"
                size="sm"
                variant={stage === item ? 'secondary' : 'ghost'}
                aria-pressed={stage === item}
                onClick={() => setStage(item)}
              >
                {STAGE_LABELS[item]}
              </Button>
            ))}
          </div>
        </div>
        {content}
      </CardContent>
    </Card>
  )
}

export function CompetencePage() {
  const model = useQuery({ queryKey: ['competence-model'], queryFn: () => api<CompetenceModel>('/competence/model/') })
  const comparison = useQuery({
    queryKey: ['competence-comparison'],
    queryFn: () => api<CompetenceComparison>('/competence/comparison/'),
  })

  let content
  if (model.isPending || comparison.isPending) {
    content = <ListSkeleton />
  } else if (model.isError || comparison.isError) {
    const error = model.error ?? comparison.error
    content = (
      <ErrorState
        error={error}
        onRetry={() => {
          void model.refetch()
          void comparison.refetch()
        }}
      />
    )
  } else if (!model.data.components.length) {
    content = (
      <EmptyState
        icon={Gauge}
        title="Kompetentlik modeli hali yaratilmagan"
        description="Namunaviy modelni yaratish: python manage.py seed_competence_model. Keyin uni admin panelda metodikangizga moslang."
      />
    )
  } else if (!comparison.data.groups.length) {
    content = <EmptyState icon={Gauge} title="Hali guruh yo'q" description="Kompetentlik guruhlaringiz talabalari bo'yicha hisoblanadi." />
  } else {
    const labels = Object.fromEntries(model.data.levels.map((level) => [level.key, level.label])) as LevelLabels
    content = (
      <div className="grid gap-4">
        <ComparisonCard model={model.data} comparison={comparison.data} labels={labels} />
        <CompetenceStatisticsCard stages={usedStages(model.data.components)} />
        <GroupCard model={model.data} comparison={comparison.data} labels={labels} />
        <ModelCard model={model.data} />
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Kompetentlik"
        description="Talabalarning ma'lumotlar bazasini loyihalash kompetentligi: komponentlar bo'yicha darajalar, tajriba boshida va oxirida. Anonim ma'lumotlar — «Tadqiqot ma'lumotlari» arxividagi kompetentlik.csv."
      />
      {content}
    </>
  )
}
