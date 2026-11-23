import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Info } from 'lucide-react'
import type { ReactNode } from 'react'

import { ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { AttritionStage, Descriptive, ExperimentAnalysis, ExperimentCohort, Normality, ParallelForms, StatTest } from '@/lib/types'
import { t } from '@/lib/i18n'

const COHORTS: ExperimentCohort[] = ['experimental', 'control']

function num(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

function pText(p: number) {
  return p < 0.001 ? '< 0.001' : p.toFixed(3)
}

/** «p = 0.012» yoki «p < 0.001» */
function pEquals(p: number) {
  return p < 0.001 ? 'p < 0.001' : `p = ${p.toFixed(3)}`
}

/** «M (SD), n» — dissertatsiya jadvallaridagi ko'rinishda */
function describe(value: Descriptive) {
  if (!value.n || value.mean === null) return '—'
  return `${value.mean.toFixed(1)} (${value.sd === null ? '—' : value.sd.toFixed(1)}), n = ${value.n}`
}

function ciText(ci: [number, number] | null | undefined) {
  return ci ? `[${num(ci[0])}; ${num(ci[1])}]` : '—'
}

function normalityText(value: Normality | null | undefined) {
  if (!value) return t('tekshirilmadi')
  return `W = ${value.w.toFixed(3)}, ${pEquals(value.p)} — ${value.normal ? t('normal') : t('normal emas')}`
}

export function TestRow({ title, test }: { title: ReactNode; test: StatTest | null }) {
  if (!test) {
    return (
      <TableRow>
        <TableCell className="font-medium">{title}</TableCell>
        <TableCell colSpan={4} className="text-sm text-muted-foreground">
          {t("Ma'lumot kam (har bir guruhda kamida 3 talaba kerak)")}
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
            {t('Nega shu mezon?')}
          </summary>
          <div className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
            <span>{test.reason}</span>
            {test.assumptions ? (
              <>
                <span>{t('Shapiro–Uilk, tajriba:')}{' '}{normalityText(test.assumptions.normality.experimental)}</span>
                <span>{t('Shapiro–Uilk, nazorat:')}{' '}{normalityText(test.assumptions.normality.control)}</span>
                <span>
                  {t('Levene:')}{' '}
                  {test.assumptions.levene
                    ? `F = ${test.assumptions.levene.f.toFixed(2)}, ${pEquals(test.assumptions.levene.p)} — ${test.assumptions.levene.equal ? t('dispersiyalar teng') : t('teng emas')}`
                    : t('tekshirilmadi')}
                </span>
              </>
            ) : test.normality !== undefined ? (
              <span>{t('Farqlar normalligi:')}{' '}{normalityText(test.normality)}</span>
            ) : null}
          </div>
        </details>
      </TableCell>
      <TableCell className="text-right tabular-nums whitespace-nowrap">
        {statistic.name}
        {statistic.df !== undefined && statistic.df !== null ? `(${statistic.df})` : ''} = {num(statistic.value)}
        {statistic.z !== undefined && statistic.z !== null ? <span className="block text-xs text-muted-foreground">{t('z =')}{' '}{num(statistic.z)}</span> : null}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {pText(test.p)}
        {test.p_holm !== undefined ? <span className="block text-xs text-muted-foreground">{t('Xolm:')}{' '}{pText(test.p_holm)}</span> : null}
        <span className="block">
          <Badge variant={(test.significant_holm ?? test.significant) ? 'default' : 'outline'}>
            {(test.significant_holm ?? test.significant) ? t('ahamiyatli') : t('ahamiyatsiz')}
          </Badge>
        </span>
      </TableCell>
      <TableCell className="text-right tabular-nums whitespace-nowrap">
        {test.effect.name} = {num(test.effect.value)}
        {test.effect.label ? <span className="block text-xs text-muted-foreground">{test.effect.label}</span> : null}
        {test.estimate ? (
          <span className="block text-xs text-muted-foreground">
            {test.estimate.name} = {num(test.estimate.value)}{t(', 95% CI')}{' '}{ciText(test.estimate.ci)}
            {test.estimate.approximate ? t(' (taxminiy)') : ''}
          </span>
        ) : null}
        {test.hedges_g ? (
          <span className="block text-xs text-muted-foreground">
            {t('g =')}{' '}{num(test.hedges_g.value)}{t(', 95% CI')}{' '}{ciText(test.hedges_g.ci)}
          </span>
        ) : null}
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
      <h3 className="text-sm font-semibold">{t('Parallel variantlar (A va B)')}</h3>
      {forms.by_kind.length ? (
        <div className="mt-2 grid gap-1 text-sm">
          {forms.by_kind.map((row) => (
            <div key={row.kind} className="tabular-nums">
              <span className="font-medium">{row.label}:</span>{' '}{t('A —')}{' '}{describe(row.A)}{t('; B —')}{' '}{describe(row.B)}
              {row.equivalence ? (
                <span className="block text-xs text-muted-foreground">
                  {t('TOST (±{margin} foiz punkti): farq', { margin: row.equivalence.margin })}{' '}{num(row.equivalence.diff, 1)}{t(', 90% oraliq [')}
                  {num(row.equivalence.ci[0], 1)}; {num(row.equivalence.ci[1], 1)}], {pEquals(row.equivalence.p)} —{' '}
                  {row.equivalence.equivalent ? t('ekvivalent') : t('ekvivalentlik isbotlanmadi')}
                </span>
              ) : null}
            </div>
          ))}
          {forms.reliability && forms.reliability.r !== null ? (
            <div className="text-muted-foreground tabular-nums">
              {t('Ikkala variantni topshirganlar (n = {n}): r =', { n: forms.reliability.n })}{' '}{num(forms.reliability.r, 3)}
            </div>
          ) : null}
          {gaps.length ? (
            <div className="text-muted-foreground">
              {t('Qiyinligi farq qiladigan juft savollar (kirish testi, > {value}%):', { value: Math.round(100 * forms.item_gap) })}{' '}
              {gaps.map((item) => `${item.order} (A ${num(item.A)}, B ${num(item.B)})`).join(', ')}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">{t("Variantli testlar yo'q: testlarga A yoki B variantni belgilang.")}</p>
      )}
      {repeated ? (
        <p className="mt-2 text-xs text-destructive">
          {t('{repeated} ta talaba kirish va chiqish testida bir xil savollarni olgan: test qilish effekti xavfi.', { repeated })}
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
          <span className={`block text-xs ${stage.level === 'yuqori' ? 'text-destructive' : 'text-muted-foreground'}`}>{t('xavf {level}', { level: stage.level })}</span>
        ) : null}
      </TableCell>
      <TableCell className="max-w-64 whitespace-normal text-sm">
        {test ? (
          <span className={test.significant ? 'text-destructive' : undefined}>
            {test.label}: {pEquals(test.p)}
          </span>
        ) : (
          '—'
        )}
        <span className="block text-xs text-muted-foreground">
          {baseline
            ? t('Tashlab ketganlar {score}: {test}, {p} — {result}', {
                score,
                test: t(baseline.label),
                p: pEquals(baseline.p),
                result: baseline.significant ? t('farq qilgan') : t("farq yo'q"),
              })
            : t('Tashlab ketganlar {score} solishtirilmadi (kamida 3 ta kerak)', { score })}
        </span>
      </TableCell>
    </TableRow>
  )
}

/** Tashlab ketish (CONSORT): guruhlar bo'yicha ulush, ularning farqi va tashlab ketganlar boshida qanday bo'lgani */
function AttritionBlock({ attrition }: { attrition: ExperimentAnalysis['attrition'] }) {
  return (
    <div className="grid gap-2 lg:col-span-2">
      <h3 className="text-sm font-semibold">{t('Tashlab ketish (attrition)')}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('Bosqich')}</TableHead>
            <TableHead className="text-right">{t('Tajriba')}</TableHead>
            <TableHead className="text-right">{t('Nazorat')}</TableHead>
            <TableHead className="text-right" title={t('Shulz va Grayms: < 5% — xavf past, > 20% — yuqori')}>
              {t('Umumiy')}
            </TableHead>
            <TableHead>{t('Guruhlar farqi')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <AttritionRow title={t('Kirish → chiqish')} stage={attrition.post} score="kirish testida" />
          {attrition.delayed ? <AttritionRow title={t('Chiqish → kechiktirilgan')} stage={attrition.delayed} score="chiqish testida" /> : null}
        </TableBody>
      </Table>
    </div>
  )
}

/** Aralashuvning bajarilishi: AI dan haqiqatda foydalanish, shart buzilishi, doza va natija */
function FidelityBlock({ fidelity }: { fidelity: ExperimentAnalysis['fidelity'] }) {
  const { dose_response: response, per_protocol: protocol } = fidelity
  return (
    <div className="rounded-xl border bg-card p-4 lg:col-span-2">
      <h3 className="text-sm font-semibold">{t('Aralashuvning bajarilishi: platformadagi AI dan foydalanish')}</h3>
      <p className="mt-1 text-xs text-muted-foreground">{t("Kirish va chiqish testlari orasidagi murojaatlar: maslahat darajalari, boshqa AI so'rovlari, chat savollari.")}</p>
      <div className="mt-2 grid gap-1 text-sm">
        {COHORTS.map((key) => {
          const cohort = fidelity.cohorts[key]
          return (
            <div key={key} className="tabular-nums">
              {key === 'experimental' ? t('Tajriba') : t('Nazorat')}{t(': {users} / {students} talaba foydalangan', { users: cohort.users, students: cohort.students })}
              {cohort.uptake === null ? '' : ` (${Math.round(100 * cohort.uptake)}%)`}{' '}{t('· mediana')}{' '}{cohort.dose.median ?? '—'}{' '}{t('· maslahat')}{' '}
              {t("{hints}, so'rov {actions}, chat {chat}", { hints: cohort.sources.hints, actions: cohort.sources.actions, chat: cohort.sources.chat })}
              {cohort.changed_condition ? t(' · sharti mos emas: {changed_condition}', { changed_condition: cohort.changed_condition }) : ''}
            </div>
          )
        })}
        <div className="text-muted-foreground tabular-nums">
          {t('Doza va natija (kuzatuv, sabab emas):')}{' '}
          {response
            ? `${t('Spirmen')} ρ = ${num(response.rho)}, 95% CI ${ciText(response.ci)}, ${pEquals(response.p)}, n = ${response.n}`
            : t("hisoblab bo'lmadi (kamida 5 talaba va har xil doza kerak)")}
        </div>
        {protocol ? (
          <div className="text-muted-foreground tabular-nums">
            {t('Per-protocol ({excluded} ta chiqarilgan): ANCOVA F({df1}, {df2}) =', { excluded: protocol.excluded, df1: protocol.df1, df2: protocol.df2 })}{' '}{num(protocol.f)}, {pEquals(protocol.p)}{t(', tuzatilgan farq')}{' '}{num(protocol.adjusted_diff)}{t(', 95% CI')}{' '}{ciText(protocol.adjusted_diff_ci)} —{' '}
            {protocol.significant ? t('ahamiyatli') : t('ahamiyatsiz')}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/** Tashqi AI vositalari (so'rovnoma): nazorat guruhining ifloslanishi va sezgirlik tahlili */
function ExternalAiBlock({ external }: { external: ExperimentAnalysis['external_ai'] }) {
  const { sensitivity } = external
  return (
    <div className="rounded-xl border bg-card p-4 lg:col-span-2">
      <h3 className="text-sm font-semibold">{t("Tashqi AI vositalari (yakuniy so'rovnoma)")}</h3>
      {external.answered ? (
        <div className="mt-2 grid gap-1 text-sm">
          {COHORTS.map((key) => {
            const cohort = external.cohorts[key]
            if (!cohort) return null
            return (
              <div key={key} className="tabular-nums">
                {key === 'experimental' ? t('Tajriba') : t('Nazorat')}{t(": o'rtacha")}{' '}{describe(cohort)}{' '}{t("· ko'p foydalanganlar (≥")}{' '}
                {external.threshold}) {cohort.heavy}
              </div>
            )
          })}
          {sensitivity ? (
            <div className="text-muted-foreground tabular-nums">
              {t('Sezgirlik tahlili ({excluded} ta chiqarilgan): ANCOVA F({df1}, {df2}) =', { excluded: sensitivity.excluded, df1: sensitivity.df1, df2: sensitivity.df2 })}{' '}
              {num(sensitivity.f)}, {pEquals(sensitivity.p)}{t(', qisman η² =')}{' '}{num(sensitivity.partial_eta2, 3)} —{' '}
              {sensitivity.significant ? t('ahamiyatli') : t('ahamiyatsiz')}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          {t("So'rovnomada tashqi AI haqidagi savollarga javob yo'q (seed_survey bilan yaratilgan so'rovnomada ular bor).")}
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
              {t("Tadqiqotga rozi bo'lgan {students} ta talaba", { students: data.students })}
              {data.excluded_no_consent ? t(' ({excluded_no_consent} tasi rozilik bermagan)', { excluded_no_consent: data.excluded_no_consent }) : ''}{t('. Hisobga kirish va chiqish testining ikkalasini topshirganlar olinadi.')}
            </span>
          </p>
        ) : null}
        {!data.quizzes.pre || !data.quizzes.post ? (
          <p className="text-sm text-muted-foreground">{t('Tahlil uchun kirish va chiqish testlari kerak.')}</p>
        ) : null}

        <div className="grid gap-2 rounded-xl border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold">{t('Xulosa')}</h3>
          <p className="text-xs text-muted-foreground">{t("Asosiy natija ko'rsatkichi (oldindan belgilangan): {label}", { label: data.primary.label })}</p>
          <ul className="grid list-disc gap-1 pl-5 text-sm">
            {data.conclusions.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>

        <div className="grid gap-2">
          <h3 className="text-sm font-semibold">{t('Tavsifiy statistika — M (SD), foizda')}</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('Guruh')}</TableHead>
                <TableHead className="text-right">{t('Kirish')}</TableHead>
                <TableHead className="text-right">{t('Chiqish')}</TableHead>
                <TableHead className="text-right">{t('Kechiktirilgan')}</TableHead>
                <TableHead className="text-right" title={t("Guruh uchun Hake o'sishi: (M chiqish − M kirish) / (100 − M kirish)")}>
                  {t('⟨g⟩')}
                </TableHead>
                <TableHead className="text-right">{t('Kirish → chiqish')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {COHORTS.map((key) => {
                const cohort = cohorts[key]
                return (
                  <TableRow key={key} className="align-top">
                    <TableCell className="font-medium">
                      {cohort.label}
                      <span className="block text-xs font-normal text-muted-foreground">{t('{groups} ta akademik guruh', { groups: cohort.groups })}</span>
                      {cohort.dropped ? (
                        <span className="block text-xs font-normal text-muted-foreground">{t('{dropped} ta chiqish testini topshirmagan', { dropped: cohort.dropped })}</span>
                      ) : null}
                      {data.quizzes.delayed && cohort.delayed_missing ? (
                        <span className="block text-xs font-normal text-muted-foreground">
                          {t('{delayed_missing} ta kechiktirilgan testni topshirmagan', { delayed_missing: cohort.delayed_missing })}
                        </span>
                      ) : null}
                      {cohort.ceiling.warning ? (
                        <span className="block text-xs font-normal text-destructive">
                          {t('Shift effekti: {students} ta talaba chiqish testida 100%', { students: cohort.ceiling.students })}
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
                        <span className="block text-xs text-muted-foreground" title={t('Kirish testida 100%: individual g aniqlanmaydi')}>
                          {t('{excluded_full_pre} ta chiqarilgan', { excluded_full_pre: cohort.gain.excluded_full_pre })}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {cohort.pre_post ? (
                        <>
                          {t('{label}: p', { label: cohort.pre_post.label })}{' '}{cohort.pre_post.p < 0.001 ? '< 0.001' : `= ${cohort.pre_post.p.toFixed(3)}`}
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
          <h3 className="text-sm font-semibold">{t('Ikkilamchi solishtiruvlar (α = {alpha}, Xolm tuzatishi bilan)', { alpha: data.alpha })}</h3>
          <p className="text-xs text-muted-foreground">
            {t("Farq: tajriba − nazorat. 95% ishonch oraliqlari Xolm bo'yicha tuzatilmagan va klasterlashni hisobga olmaydi.")}
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('Nima solishtiriladi')}</TableHead>
                <TableHead>{t('Mezon (avtomatik tanlangan)')}</TableHead>
                <TableHead className="text-right">{t('Statistika@@ustun')}</TableHead>
                <TableHead className="text-right">{t('p')}</TableHead>
                <TableHead className="text-right">{t('Effekt')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TestRow title={t("Boshlang'ich tenglik (kirish testi)")} test={data.baseline} />
              <TestRow title={t('Chiqish testi')} test={data.comparisons.post} />
              <TestRow title={t("Hake o'sishi (g)")} test={data.comparisons.gain} />
              {data.quizzes.delayed ? <TestRow title={t('Kechiktirilgan test')} test={data.comparisons.delayed} /> : null}
            </TableBody>
          </Table>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-xl border bg-card p-4">
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              {t('ANCOVA: chiqish ~ guruh + kirish')}
              {ancova?.primary ? <Badge>{t('asosiy gipoteza')}</Badge> : null}
            </h3>
            {ancova ? (
              <div className="mt-2 grid gap-1 text-sm">
                <div className="tabular-nums">
                  {t('F({df1}, {df2}) =', { df1: ancova.df1, df2: ancova.df2 })}{' '}{num(ancova.f)}{t(', p')}{' '}{ancova.p < 0.001 ? '< 0.001' : `= ${ancova.p.toFixed(3)}`}{t(', qisman η² =')}{' '}
                  {num(ancova.partial_eta2, 3)} ({ancova.effect_label})
                </div>
                <div className="text-muted-foreground tabular-nums">
                  {t("Tuzatilgan o'rtachalar: tajriba")}{' '}{num(ancova.adjusted_means.experimental, 1)}{t('%, nazorat')}{' '}{num(ancova.adjusted_means.control, 1)}%
                </div>
                <div className="tabular-nums">
                  {t('Tuzatilgan farq:')}{' '}{num(ancova.adjusted_diff)}{' '}{t('ball, 95% CI')}{' '}{ciText(ancova.adjusted_diff_ci)}
                  {ancova.hedges_g ? `; g = ${num(ancova.hedges_g.value)}, 95% CI ${ciText(ancova.hedges_g.ci)}` : ''}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('Regressiya chiziqlari parallelligi:')}{' '}
                  {ancova.slopes
                    ? `F = ${num(ancova.slopes.f)}, ${pEquals(ancova.slopes.p)} — ${ancova.slopes.parallel ? t('shart bajarilgan') : t("shart buzilgan, ehtiyot bo'ling")}`
                    : t('tekshirilmadi')}
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                {data.ancova_unavailable ?? t("Ma'lumot kam: ikkala guruhda kirish va chiqish natijalari kerak.")}
              </p>
            )}
          </div>
          <div className="rounded-xl border bg-card p-4">
            <h3 className="text-sm font-semibold">{t('Statistik quvvat (α = {alpha}, maqsad {value}%)', { alpha: power.alpha, value: Math.round(100 * power.target) })}</h3>
            <div className="mt-2 grid gap-1 text-sm">
              <div className="tabular-nums">
                {t('Kuzatilgan effekt d =')}{' '}{num(power.observed_d)}{' '}{t('· erishilgan quvvat')}{' '}
                {power.achieved === null ? '—' : `${Math.round(100 * power.achieved)}%`}
              </div>
              <div className="text-muted-foreground tabular-nums">
                {t('Har bir guruhda kerakli talabalar: kuzatilgan effekt uchun')}{' '}{power.required_per_group_observed ?? '—'}{t(", o'rta effekt (d = 0.5) uchun {required_per_group_medium}", { required_per_group_medium: power.required_per_group_medium })}
              </div>
              {power.approximate ? <div className="text-xs text-muted-foreground">{t('Normal yaqinlashish: aniq qiymatdan ±3% farq qilishi mumkin.')}</div> : null}
            </div>
          </div>
          <AttritionBlock attrition={data.attrition} />
          <FormsBlock forms={data.forms} />
          <FidelityBlock fidelity={data.fidelity} />
          <ExternalAiBlock external={data.external_ai} />
          <div className="rounded-xl border bg-card p-4 lg:col-span-2">
            <h3 className="text-sm font-semibold">{t("Klasterlash: akademik guruhlar ta'siri")}</h3>
            <div className="mt-2 grid gap-1 text-sm">
              <div className="tabular-nums">
                {t('Guruhlar soni: tajriba {experimental}, nazorat {control}', { experimental: data.clustering.groups.experimental, control: data.clustering.groups.control })}
              </div>
              {data.clustering.confounded ? (
                <div className="text-muted-foreground">
                  {t("Kamida bitta shartda bitta guruh: AI ta'sirini guruh ta'siridan ajratib bo'lmaydi (kvazi-tajriba). Har bir shartga ikki va undan ko'p guruh oling.")}
                </div>
              ) : data.clustering.icc ? (
                <div className="text-muted-foreground tabular-nums">
                  {t('ICC(1) =')}{' '}{num(data.clustering.icc.value, 3)}{' '}{t('(F =')}{' '}{num(data.clustering.icc.f)}, {pEquals(data.clustering.icc.p)}{t(') · dizayn effekti')}{' '}{num(data.clustering.icc.design_effect)}{' '}{t('· samarali talabalar soni ≈')}{' '}
                  {num(data.clustering.icc.effective_n, 1)}
                </div>
              ) : (
                <div className="text-muted-foreground">{t("Ma'lumot kam.")}</div>
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
        <CardTitle>{t('Tajriba natijasi: statistik tahlil')}</CardTitle>
        <CardDescription>
          {t("Barcha ruxsat etilgan guruhlar bo'yicha (guruh tanlovi bu yerga ta'sir qilmaydi). Mezon shartlarga qarab tanlanadi: ikkala guruhda taqsimot normal va dispersiyalar teng bo'lsa — Styudent t, teng bo'lmasa — Uelch t, normal bo'lmasa — Mann–Uitni U.")}
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
