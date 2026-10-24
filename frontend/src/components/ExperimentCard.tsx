import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Info } from 'lucide-react'
import type { ReactNode } from 'react'

import { ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { AttritionStage, Descriptive, ExperimentAnalysis, ExperimentCohort, Normality, ParallelForms, StatTest } from '@/lib/types'

const COHORTS: ExperimentCohort[] = ['experimental', 'control']

function num(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

function pText(p: number) {
  return p < 0.001 ? '< 0.001' : p.toFixed(3)
}

/** «M (SD), n» — dissertatsiya jadvallaridagi ko'rinishda */
function describe(value: Descriptive) {
  if (!value.n || value.mean === null) return '—'
  return `${value.mean.toFixed(1)} (${value.sd === null ? '—' : value.sd.toFixed(1)}), n = ${value.n}`
}

function normalityText(value: Normality | null | undefined) {
  if (!value) return 'tekshirilmadi'
  return `W = ${value.w.toFixed(3)}, p = ${pText(value.p)} — ${value.normal ? 'normal' : 'normal emas'}`
}

export function TestRow({ title, test }: { title: ReactNode; test: StatTest | null }) {
  if (!test) {
    return (
      <TableRow>
        <TableCell className="font-medium">{title}</TableCell>
        <TableCell colSpan={4} className="text-sm text-muted-foreground">
          Ma'lumot kam (har bir guruhda kamida 3 talaba kerak)
        </TableCell>
      </TableRow>
    )
  }
  const { statistic } = test
  return (
    <TableRow className="align-top">
      <TableCell className="font-medium">{title}</TableCell>
      <TableCell className="max-w-64 whitespace-normal">
        <div>{test.label}</div>
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden="true" />
            Nega shu mezon?
          </summary>
          <div className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
            <span>{test.reason}</span>
            {test.assumptions ? (
              <>
                <span>Shapiro–Uilk, tajriba: {normalityText(test.assumptions.normality.experimental)}</span>
                <span>Shapiro–Uilk, nazorat: {normalityText(test.assumptions.normality.control)}</span>
                <span>
                  Levene:{' '}
                  {test.assumptions.levene
                    ? `F = ${test.assumptions.levene.f.toFixed(2)}, p = ${pText(test.assumptions.levene.p)} — ${test.assumptions.levene.equal ? 'dispersiyalar teng' : 'teng emas'}`
                    : 'tekshirilmadi'}
                </span>
              </>
            ) : test.normality !== undefined ? (
              <span>Farqlar normalligi: {normalityText(test.normality)}</span>
            ) : null}
          </div>
        </details>
      </TableCell>
      <TableCell className="text-right tabular-nums whitespace-nowrap">
        {statistic.name}
        {statistic.df !== undefined && statistic.df !== null ? `(${statistic.df})` : ''} = {num(statistic.value)}
        {statistic.z !== undefined && statistic.z !== null ? <span className="block text-xs text-muted-foreground">z = {num(statistic.z)}</span> : null}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {pText(test.p)}
        {test.p_holm !== undefined ? <span className="block text-xs text-muted-foreground">Xolm: {pText(test.p_holm)}</span> : null}
        <span className="block">
          <Badge variant={(test.significant_holm ?? test.significant) ? 'default' : 'outline'}>
            {(test.significant_holm ?? test.significant) ? 'ahamiyatli' : 'ahamiyatsiz'}
          </Badge>
        </span>
      </TableCell>
      <TableCell className="text-right tabular-nums whitespace-nowrap">
        {test.effect.name} = {num(test.effect.value)}
        {test.effect.label ? <span className="block text-xs text-muted-foreground">{test.effect.label}</span> : null}
      </TableCell>
    </TableRow>
  )
}

/** Parallel variantlar (A/B): ekvivalentlik (TOST), ishonchlilik, juft savollar qiyinligi */
function FormsBlock({ forms }: { forms: ParallelForms }) {
  const gaps = forms.items.filter((item) => item.gap)
  const repeated = forms.same_form + forms.without_form
  return (
    <div className="rounded-xl border bg-card p-4 lg:col-span-2">
      <h3 className="text-sm font-semibold">Parallel variantlar (A va B)</h3>
      {forms.by_kind.length ? (
        <div className="mt-2 grid gap-1 text-sm">
          {forms.by_kind.map((row) => (
            <div key={row.kind} className="tabular-nums">
              <span className="font-medium">{row.label}:</span> A — {describe(row.A)}; B — {describe(row.B)}
              {row.equivalence ? (
                <span className="block text-xs text-muted-foreground">
                  TOST (±{row.equivalence.margin} foiz punkti): farq {num(row.equivalence.diff, 1)}, 90% oraliq [
                  {num(row.equivalence.ci[0], 1)}; {num(row.equivalence.ci[1], 1)}], p = {pText(row.equivalence.p)} —{' '}
                  {row.equivalence.equivalent ? 'ekvivalent' : 'ekvivalentlik isbotlanmadi'}
                </span>
              ) : null}
            </div>
          ))}
          {forms.reliability && forms.reliability.r !== null ? (
            <div className="text-muted-foreground tabular-nums">
              Ikkala variantni topshirganlar (n = {forms.reliability.n}): r = {num(forms.reliability.r, 3)}
            </div>
          ) : null}
          {gaps.length ? (
            <div className="text-muted-foreground">
              Qiyinligi farq qiladigan juft savollar (kirish testi, &gt; {Math.round(100 * forms.item_gap)}%):{' '}
              {gaps.map((item) => `${item.order} (A ${num(item.A)}, B ${num(item.B)})`).join(', ')}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Variantli testlar yo'q: testlarga A yoki B variantni belgilang.</p>
      )}
      {repeated ? (
        <p className="mt-2 text-xs text-destructive">
          {repeated} ta talaba kirish va chiqish testida bir xil savollarni olgan: test qilish effekti xavfi.
        </p>
      ) : null}
    </div>
  )
}

function percentText(value: number | null) {
  return value === null ? '—' : `${Math.round(100 * value)}%`
}

function AttritionRow({ title, stage, score }: { title: string; stage: AttritionStage; score: string }) {
  const { test, baseline } = stage
  return (
    <TableRow className="align-top">
      <TableCell className="font-medium">{title}</TableCell>
      {COHORTS.map((key) => (
        <TableCell key={key} className="text-right tabular-nums">
          {stage.cohorts[key].lost} / {stage.cohorts[key].started}
          <span className="block text-xs text-muted-foreground">{percentText(stage.cohorts[key].rate)}</span>
        </TableCell>
      ))}
      <TableCell className="text-right tabular-nums">
        {percentText(stage.overall)}
        {stage.level ? (
          <span className={`block text-xs ${stage.level === 'yuqori' ? 'text-destructive' : 'text-muted-foreground'}`}>xavf {stage.level}</span>
        ) : null}
      </TableCell>
      <TableCell className="max-w-64 whitespace-normal text-sm">
        {test ? (
          <span className={test.significant ? 'text-destructive' : undefined}>
            {test.label}: p = {pText(test.p)}
          </span>
        ) : (
          '—'
        )}
        <span className="block text-xs text-muted-foreground">
          {baseline
            ? `Tashlab ketganlar ${score}: ${baseline.label}, p = ${pText(baseline.p)} — ${baseline.significant ? 'farq qilgan' : "farq yo'q"}`
            : `Tashlab ketganlar ${score} solishtirilmadi (kamida 3 ta kerak)`}
        </span>
      </TableCell>
    </TableRow>
  )
}

/** Tashlab ketish (CONSORT): guruhlar bo'yicha ulush, ularning farqi va tashlab ketganlar boshida qanday bo'lgani */
function AttritionBlock({ attrition }: { attrition: ExperimentAnalysis['attrition'] }) {
  return (
    <div className="grid gap-2 lg:col-span-2">
      <h3 className="text-sm font-semibold">Tashlab ketish (attrition)</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Bosqich</TableHead>
            <TableHead className="text-right">Tajriba</TableHead>
            <TableHead className="text-right">Nazorat</TableHead>
            <TableHead className="text-right" title="Shulz va Grayms: < 5% — xavf past, > 20% — yuqori">
              Umumiy
            </TableHead>
            <TableHead>Guruhlar farqi</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <AttritionRow title="Kirish → chiqish" stage={attrition.post} score="kirish testida" />
          {attrition.delayed ? <AttritionRow title="Chiqish → kechiktirilgan" stage={attrition.delayed} score="chiqish testida" /> : null}
        </TableBody>
      </Table>
    </div>
  )
}

/** Tashqi AI vositalari (so'rovnoma): nazorat guruhining ifloslanishi va sezgirlik tahlili */
function ExternalAiBlock({ external }: { external: ExperimentAnalysis['external_ai'] }) {
  const { sensitivity } = external
  return (
    <div className="rounded-xl border bg-card p-4 lg:col-span-2">
      <h3 className="text-sm font-semibold">Tashqi AI vositalari (yakuniy so'rovnoma)</h3>
      {external.answered ? (
        <div className="mt-2 grid gap-1 text-sm">
          {COHORTS.map((key) => {
            const cohort = external.cohorts[key]
            if (!cohort) return null
            return (
              <div key={key} className="tabular-nums">
                {key === 'experimental' ? 'Tajriba' : 'Nazorat'}: o'rtacha {describe(cohort)} · ko'p foydalanganlar (≥{' '}
                {external.threshold}) {cohort.heavy}
              </div>
            )
          })}
          {sensitivity ? (
            <div className="text-muted-foreground tabular-nums">
              Sezgirlik tahlili ({sensitivity.excluded} ta chiqarilgan): ANCOVA F({sensitivity.df1}, {sensitivity.df2}) ={' '}
              {num(sensitivity.f)}, p = {pText(sensitivity.p)}, qisman η² = {num(sensitivity.partial_eta2, 3)} —{' '}
              {sensitivity.significant ? 'ahamiyatli' : 'ahamiyatsiz'}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          So'rovnomada tashqi AI haqidagi savollarga javob yo'q (seed_survey bilan yaratilgan so'rovnomada ular bor).
        </p>
      )}
    </div>
  )
}

/** Tajriba natijasining statistik tahlili: tavsifiy statistika, Hake o'sishi, mezonni avtomatik tanlash, ANCOVA, quvvat */
export function ExperimentCard() {
  const analysis = useQuery({ queryKey: ['experiment'], queryFn: () => api<ExperimentAnalysis>('/experiment/') })

  let content
  if (analysis.isPending) content = <ListSkeleton rows={3} />
  else if (analysis.isError) content = <ErrorState error={analysis.error} onRetry={() => void analysis.refetch()} />
  else {
    const data = analysis.data
    const { cohorts, ancova, power } = data
    content = (
      <div className="grid gap-5">
        {data.consent_required ? (
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              Tadqiqotga rozi bo'lgan {data.students} ta talaba
              {data.excluded_no_consent ? ` (${data.excluded_no_consent} tasi rozilik bermagan)` : ''}. Hisobga kirish va
              chiqish testining ikkalasini topshirganlar olinadi.
            </span>
          </p>
        ) : null}
        {!data.quizzes.pre || !data.quizzes.post ? (
          <p className="text-sm text-muted-foreground">Tahlil uchun kirish va chiqish testlari kerak.</p>
        ) : null}

        <div className="grid gap-2 rounded-xl border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold">Xulosa</h3>
          <p className="text-xs text-muted-foreground">Asosiy natija ko'rsatkichi (oldindan belgilangan): {data.primary.label}</p>
          <ul className="grid list-disc gap-1 pl-5 text-sm">
            {data.conclusions.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>

        <div className="grid gap-2">
          <h3 className="text-sm font-semibold">Tavsifiy statistika — M (SD), foizda</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Guruh</TableHead>
                <TableHead className="text-right">Kirish</TableHead>
                <TableHead className="text-right">Chiqish</TableHead>
                <TableHead className="text-right">Kechiktirilgan</TableHead>
                <TableHead className="text-right" title="Guruh uchun Hake o'sishi: (M chiqish − M kirish) / (100 − M kirish)">
                  ⟨g⟩
                </TableHead>
                <TableHead className="text-right">Kirish → chiqish</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {COHORTS.map((key) => {
                const cohort = cohorts[key]
                return (
                  <TableRow key={key} className="align-top">
                    <TableCell className="font-medium">
                      {cohort.label}
                      <span className="block text-xs font-normal text-muted-foreground">{cohort.groups} ta akademik guruh</span>
                      {cohort.dropped ? (
                        <span className="block text-xs font-normal text-muted-foreground">{cohort.dropped} ta chiqish testini topshirmagan</span>
                      ) : null}
                      {data.quizzes.delayed && cohort.delayed_missing ? (
                        <span className="block text-xs font-normal text-muted-foreground">
                          {cohort.delayed_missing} ta kechiktirilgan testni topshirmagan
                        </span>
                      ) : null}
                      {cohort.ceiling.warning ? (
                        <span className="block text-xs font-normal text-destructive">
                          Shift effekti: {cohort.ceiling.students} ta talaba chiqish testida 100%
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{describe(cohort.pre)}</TableCell>
                    <TableCell className="text-right tabular-nums">{describe(cohort.post)}</TableCell>
                    <TableCell className="text-right tabular-nums">{describe(cohort.delayed)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {num(cohort.gain.class)}
                      {cohort.gain.level ? <span className="block text-xs text-muted-foreground">{cohort.gain.level}</span> : null}
                      {cohort.gain.excluded_full_pre ? (
                        <span className="block text-xs text-muted-foreground" title="Kirish testida 100%: individual g aniqlanmaydi">
                          {cohort.gain.excluded_full_pre} ta chiqarilgan
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {cohort.pre_post ? (
                        <>
                          {cohort.pre_post.label}: p {cohort.pre_post.p < 0.001 ? '< 0.001' : `= ${cohort.pre_post.p.toFixed(3)}`}
                          <span className="block text-xs text-muted-foreground">
                            {cohort.pre_post.effect.name} = {num(cohort.pre_post.effect.value)} ({cohort.pre_post.effect.label})
                          </span>
                        </>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>

        <div className="grid gap-2">
          <h3 className="text-sm font-semibold">Ikkilamchi solishtiruvlar (α = {data.alpha}, Xolm tuzatishi bilan)</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nima solishtiriladi</TableHead>
                <TableHead>Mezon (avtomatik tanlangan)</TableHead>
                <TableHead className="text-right">Statistika</TableHead>
                <TableHead className="text-right">p</TableHead>
                <TableHead className="text-right">Effekt</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TestRow title="Boshlang'ich tenglik (kirish testi)" test={data.baseline} />
              <TestRow title="Chiqish testi" test={data.comparisons.post} />
              <TestRow title="Hake o'sishi (g)" test={data.comparisons.gain} />
              {data.quizzes.delayed ? <TestRow title="Kechiktirilgan test" test={data.comparisons.delayed} /> : null}
            </TableBody>
          </Table>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-xl border bg-card p-4">
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              ANCOVA: chiqish ~ guruh + kirish
              {ancova?.primary ? <Badge>asosiy gipoteza</Badge> : null}
            </h3>
            {ancova ? (
              <div className="mt-2 grid gap-1 text-sm">
                <div className="tabular-nums">
                  F({ancova.df1}, {ancova.df2}) = {num(ancova.f)}, p {ancova.p < 0.001 ? '< 0.001' : `= ${ancova.p.toFixed(3)}`}, qisman η² ={' '}
                  {num(ancova.partial_eta2, 3)} ({ancova.effect_label})
                </div>
                <div className="text-muted-foreground tabular-nums">
                  Tuzatilgan o'rtachalar: tajriba {num(ancova.adjusted_means.experimental, 1)}%, nazorat {num(ancova.adjusted_means.control, 1)}%
                </div>
                <div className="text-xs text-muted-foreground">
                  Regressiya chiziqlari parallelligi:{' '}
                  {ancova.slopes
                    ? `F = ${num(ancova.slopes.f)}, p = ${pText(ancova.slopes.p)} — ${ancova.slopes.parallel ? 'shart bajarilgan' : "shart buzilgan, ehtiyot bo'ling"}`
                    : 'tekshirilmadi'}
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">Ma'lumot kam: ikkala guruhda kirish va chiqish natijalari kerak.</p>
            )}
          </div>
          <div className="rounded-xl border bg-card p-4">
            <h3 className="text-sm font-semibold">Statistik quvvat (α = {power.alpha}, maqsad {Math.round(100 * power.target)}%)</h3>
            <div className="mt-2 grid gap-1 text-sm">
              <div className="tabular-nums">
                Kuzatilgan effekt d = {num(power.observed_d)} · erishilgan quvvat{' '}
                {power.achieved === null ? '—' : `${Math.round(100 * power.achieved)}%`}
              </div>
              <div className="text-muted-foreground tabular-nums">
                Har bir guruhda kerakli talabalar: kuzatilgan effekt uchun {power.required_per_group_observed ?? '—'}, o'rta effekt (d =
                0.5) uchun {power.required_per_group_medium}
              </div>
              {power.approximate ? <div className="text-xs text-muted-foreground">Normal yaqinlashish: aniq qiymatdan ±3% farq qilishi mumkin.</div> : null}
            </div>
          </div>
          <AttritionBlock attrition={data.attrition} />
          <FormsBlock forms={data.forms} />
          <ExternalAiBlock external={data.external_ai} />
          <div className="rounded-xl border bg-card p-4 lg:col-span-2">
            <h3 className="text-sm font-semibold">Klasterlash: akademik guruhlar ta'siri</h3>
            <div className="mt-2 grid gap-1 text-sm">
              <div className="tabular-nums">
                Guruhlar soni: tajriba {data.clustering.groups.experimental}, nazorat {data.clustering.groups.control}
              </div>
              {data.clustering.confounded ? (
                <div className="text-muted-foreground">
                  Kamida bitta shartda bitta guruh: AI ta'sirini guruh ta'siridan ajratib bo'lmaydi (kvazi-tajriba). Har bir shartga
                  ikki va undan ko'p guruh oling.
                </div>
              ) : data.clustering.icc ? (
                <div className="text-muted-foreground tabular-nums">
                  ICC(1) = {num(data.clustering.icc.value, 3)} (F = {num(data.clustering.icc.f)}, p = {pText(data.clustering.icc.p)}) ·
                  dizayn effekti {num(data.clustering.icc.design_effect)} · samarali talabalar soni ≈{' '}
                  {num(data.clustering.icc.effective_n, 1)}
                </div>
              ) : (
                <div className="text-muted-foreground">Ma'lumot kam.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tajriba natijasi: statistik tahlil</CardTitle>
        <CardDescription>
          Barcha ruxsat etilgan guruhlar bo'yicha (guruh tanlovi bu yerga ta'sir qilmaydi). Mezon shartlarga qarab tanlanadi:
          ikkala guruhda taqsimot normal va dispersiyalar teng bo'lsa — Styudent t, teng bo'lmasa — Uelch t, normal bo'lmasa —
          Mann–Uitni U.
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
