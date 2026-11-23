import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, CircleCheck, Database, Loader2, Save, Send } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormField } from '@/components/FormField'
import { ErrorState, ListSkeleton } from '@/components/States'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { ExpertInfo, ExpertItem, ExpertPage as ExpertPageData, ExpertRating } from '@/lib/types'
import { cn } from '@/lib/utils'
import { localized, t } from '@/lib/i18n'

const ESSENTIAL = localized([
  { value: 3, label: 'Zarur' },
  { value: 2, label: "Foydali, lekin zarur emas" },
  { value: 1, label: 'Keraksiz' },
])
const RELEVANCE = localized([
  { value: 1, label: 'Mos emas' },
  { value: 2, label: 'Qisman mos' },
  { value: 3, label: 'Mos' },
  { value: 4, label: 'Juda mos' },
])
const CLARITY = localized([
  { value: 1, label: 'Tushunarsiz' },
  { value: 2, label: 'Qayta yozish kerak' },
  { value: 3, label: 'Tushunarli' },
  { value: 4, label: 'Juda aniq' },
])
const SCALES = ['essential', 'relevance', 'clarity'] as const

function Scale({
  name,
  legend,
  options,
  value,
  disabled,
  onChange,
}: {
  name: string
  legend: string
  options: { value: number; label: string }[]
  value: number | undefined
  disabled: boolean
  onChange: (value: number) => void
}) {
  return (
    <fieldset className="grid gap-1.5">
      <legend className="text-sm font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <label
            key={option.value}
            className={cn(
              'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50',
              value === option.value ? 'border-primary bg-primary/10 text-primary' : 'hover:bg-muted',
              disabled && 'cursor-default opacity-70',
            )}
          >
            <input
              type="radio"
              className="sr-only"
              name={name}
              value={option.value}
              checked={value === option.value}
              disabled={disabled}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function ItemCard({
  item,
  rating,
  disabled,
  onChange,
}: {
  item: ExpertItem
  rating: ExpertRating
  disabled: boolean
  onChange: (rating: ExpertRating) => void
}) {
  const done = SCALES.every((scale) => rating[scale] !== undefined)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-start gap-2 text-base">
          {done ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-label="baholangan" /> : null}
          <span className="whitespace-pre-wrap">
            {item.order}. {item.text}
          </span>
        </CardTitle>
        {item.kind === 'likert' ? (
          <CardDescription>{t("So'rovnoma fikri: talaba 1 dan 5 gacha shkalada qo'shiladi yoki qo'shilmaydi.")}</CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="grid gap-4">
        {item.choices.length ? (
          <ul className="grid gap-1" aria-label={t('Javob variantlari')}>
            {item.choices.map((choice, index) => (
              <li
                key={index}
                className={cn('flex items-center gap-2 rounded-md px-2 py-1 text-sm', choice.is_correct && 'bg-emerald-50 text-emerald-900')}
              >
                {choice.is_correct ? <CircleCheck className="size-4 shrink-0" aria-label={t("to'g'ri javob")} /> : <span className="size-4 shrink-0" />}
                {choice.text}
              </li>
            ))}
          </ul>
        ) : null}
        <Scale
          name={`essential-${item.key}`}
          legend={t("Savol o'lchanadigan tushuncha uchun zarurmi?")}
          options={ESSENTIAL}
          value={rating.essential}
          disabled={disabled}
          onChange={(value) => onChange({ ...rating, essential: value })}
        />
        <Scale
          name={`relevance-${item.key}`}
          legend={t('Mavzuga mosligi')}
          options={RELEVANCE}
          value={rating.relevance}
          disabled={disabled}
          onChange={(value) => onChange({ ...rating, relevance: value })}
        />
        <Scale
          name={`clarity-${item.key}`}
          legend={t('Ifodasi va variantlarining aniqligi')}
          options={CLARITY}
          value={rating.clarity}
          disabled={disabled}
          onChange={(value) => onChange({ ...rating, clarity: value })}
        />
        <FormField id={`comment-${item.key}`} label={t('Izoh yoki taklif (ixtiyoriy)')}>
          <Textarea
            id={`comment-${item.key}`}
            rows={2}
            maxLength={1000}
            disabled={disabled}
            value={rating.comment ?? ''}
            onChange={(event) => onChange({ ...rating, comment: event.target.value })}
          />
        </FormField>
      </CardContent>
    </Card>
  )
}

function ExpertForm({ token, page }: { token: string; page: ExpertPageData }) {
  const [expert, setExpert] = useState<ExpertInfo>(page.expert)
  const [ratings, setRatings] = useState<Record<string, ExpertRating>>(page.ratings)
  const [submittedAt, setSubmittedAt] = useState(page.submitted_at)
  const [confirming, setConfirming] = useState(false)
  const locked = Boolean(submittedAt) || !page.open
  const rated = page.items.filter((item) => SCALES.every((scale) => ratings[item.key]?.[scale] !== undefined)).length

  const save = useMutation({
    mutationFn: (submit: boolean) =>
      api<ExpertPageData>(`/expert/${token}/`, { method: 'PUT', auth: false, body: { expert, ratings, submit } }),
    onSuccess: (data, submit) => {
      setSubmittedAt(data.submitted_at)
      setConfirming(false)
      toast.success(submit ? t('Rahmat! Baholaringiz yuborildi') : t('Saqlandi. Keyinroq shu havola orqali davom ettirishingiz mumkin'))
    },
    onError: (error) => {
      setConfirming(false)
      toast.error(errorMessage(error))
    },
  })

  return (
    <div className="grid gap-4">
      {submittedAt ? (
        <Alert>
          <CheckCircle2 aria-hidden="true" />
          <AlertDescription>{t('Baholaringiz {submittedAt} da yuborilgan. Rahmat!', { submittedAt: formatDateTime(submittedAt) })}</AlertDescription>
        </Alert>
      ) : !page.open ? (
        <Alert variant="destructive">
          <AlertDescription>{t('Baholash muddati tugagan.')}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t('Ekspert haqida')}</CardTitle>
          <CardDescription>{t("Ekspertlar ro'yxati dissertatsiya ilovasida keltiriladi. Ism-familiya majburiy.")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          {(
            [
              ['full_name', t('Familiya, ism, otasining ismi'), 200],
              ['degree', t('Ilmiy daraja va unvon (masalan, t.f.n., dotsent)'), 200],
              ['position', t('Lavozim'), 200],
              ['workplace', t('Ish joyi'), 300],
            ] as const
          ).map(([field, label, max]) => (
            <FormField key={field} id={`expert-${field}`} label={label}>
              <Input
                id={`expert-${field}`}
                className="h-10"
                maxLength={max}
                disabled={locked}
                value={(expert[field] as string | undefined) ?? ''}
                onChange={(event) => setExpert({ ...expert, [field]: event.target.value })}
              />
            </FormField>
          ))}
          <FormField id="expert-experience" label={t("Fan bo'yicha pedagogik staj (yil)")}>
            <Input
              id="expert-experience"
              type="number"
              min={0}
              max={70}
              className="h-10 w-28"
              disabled={locked}
              value={expert.experience_years ?? ''}
              onChange={(event) =>
                setExpert({ ...expert, experience_years: event.target.value === '' ? null : Number(event.target.value) })
              }
            />
          </FormField>
        </CardContent>
      </Card>

      {page.items.map((item) => (
        <ItemCard
          key={item.key}
          item={item}
          rating={ratings[item.key] ?? {}}
          disabled={locked}
          onChange={(rating) => setRatings({ ...ratings, [item.key]: rating })}
        />
      ))}

      {locked ? null : (
        <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-background/95 p-3 backdrop-blur">
          <span className="text-sm text-muted-foreground tabular-nums">
            {t('Baholangan: {rated} / {length}', { rated, length: page.items.length })}
          </span>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="lg" disabled={save.isPending} onClick={() => save.mutate(false)}>
              <Save aria-hidden="true" />
              {t('Saqlash')}
            </Button>
            <Button size="lg" disabled={save.isPending || rated < page.items.length || !expert.full_name?.trim()} onClick={() => setConfirming(true)}>
              {save.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
              {t('Yuborish')}
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        title={t('Baholarni yuborish')}
        description={t("Yuborilgandan keyin baholarni o'zgartirib bo'lmaydi.")}
        confirmLabel={t('Yuborish')}
        pending={save.isPending}
        onConfirm={() => save.mutate(true)}
        onClose={() => setConfirming(false)}
      />
    </div>
  )
}

/** Ekspert sahifasi: login talab qilinmaydi, shaxsiy havola orqali ochiladi */
export function ExpertPage() {
  const { token = '' } = useParams()
  const page = useQuery({
    queryKey: ['expert-page', token],
    queryFn: () => api<ExpertPageData>(`/expert/${encodeURIComponent(token)}/`, { auth: false }),
    retry: false,
    refetchOnWindowFocus: false,
  })

  let content
  if (page.isPending) content = <ListSkeleton />
  else if (page.isError) content = <ErrorState error={page.error} onRetry={() => void page.refetch()} />
  else
    content = (
      <>
        <header className="grid gap-2">
          <h1 className="font-heading text-2xl font-semibold text-heading">{page.data.title}</h1>
          <p className="text-sm text-muted-foreground">
            {t('«{quiz_title}» savollarini ekspert sifatida baholash', { quiz_title: page.data.quiz_title })}
            {page.data.closes_at ? t(' · {closes_at} gacha', { closes_at: formatDateTime(page.data.closes_at) }) : ''}
          </p>
        </header>
        <Card>
          <CardHeader>
            <CardTitle>{t("Ko'rsatma")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm leading-relaxed">
            <p>
              <span className="font-medium">{t("O'lchanadigan tushuncha:")}{' '}</span>
              {page.data.construct}
            </p>
            {page.data.instructions ? <p className="whitespace-pre-wrap">{page.data.instructions}</p> : null}
            <p className="text-muted-foreground">
              {t("Har bir savolni uch mezon bo'yicha baholang: zarurligi, mavzuga mosligi va aniqligi. To'g'ri javoblar yashil bilan belgilangan. Javoblaringizni «Saqlash» bilan saqlab, keyinroq shu havola orqali davom ettirishingiz mumkin. Havolani boshqalarga bermang: unda test javoblari bor.")}
            </p>
          </CardContent>
        </Card>
        <ExpertForm token={token} page={page.data} />
      </>
    )

  return (
    <div className="min-h-svh bg-muted/40">
      <div className="mx-auto grid w-full max-w-3xl gap-4 p-4 lg:p-6">
        <div className="flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Database className="size-5" aria-hidden="true" />
          </div>
          <div className="text-sm font-semibold">{t('MB loyihalash · ekspert baholashi')}</div>
        </div>
        {content}
      </div>
    </div>
  )
}
