import { CircleCheck, CircleX, Plus, ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react'

import { SqlCode } from '@/components/SqlCode'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { LabProbe, LabProbeResult, LabRunResult } from '@/lib/types'
import { localized, t } from '@/lib/i18n'

const KIND_LABELS: Record<LabProbe['kind'], string> = localized({
  attack: 'Hujum',
  valid: "To'g'ri ma'lumot",
})

function KindBadge({ kind }: { kind: LabProbe['kind'] }) {
  return (
    <Badge variant={kind === 'attack' ? 'destructive' : 'secondary'} className="shrink-0">
      {kind === 'attack' ? <ShieldAlert aria-hidden="true" /> : <ShieldCheck aria-hidden="true" />}
      {KIND_LABELS[kind]}
    </Badge>
  )
}

/** Talabaga laboratoriya shartida: qaysi sinovlar bajariladi (SQL bilan) */
export function ProbeList({ probes, hidden }: { probes: LabProbe[]; hidden: number }) {
  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        {t("Kodingizdan keyin har bir sinov alohida bajariladi va orqaga qaytariladi. Hujumni cheklov (CHECK, FOREIGN KEY, UNIQUE, NOT NULL yoki trigger) rad etishi, to'g'ri ma'lumotni esa qabul qilishi kerak.")}
        {hidden ? t(" Bundan tashqari {hidden} ta yashirin sinov bor: cheklov faqat shu misollarga emas, qoidaning o'ziga mos bo'lsin.", { hidden }) : ''}
      </p>
      <ul className="grid gap-3">
        {probes.map((probe) => (
          <li key={probe.id} className="grid gap-1.5">
            <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
              <KindBadge kind={probe.kind} />
              {probe.title}
            </div>
            <SqlCode code={probe.sql} />
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Tekshiruv natijasi: har bir ko'rinadigan sinov va yashirinlar soni */
export function ProbeResults({ result }: { result: LabRunResult }) {
  const items = result.probes ?? []
  if (!items.length && !result.hidden_probes?.total) return null
  const passed = items.filter((item) => item.passed).length + (result.hidden_probes?.passed ?? 0)
  const total = items.length + (result.hidden_probes?.total ?? 0)
  return (
    <div className="grid gap-2 rounded-lg border p-3">
      <div className="text-sm font-medium">
        {t("Sinovlar: {passed} / {total} o'tdi", { passed, total })}
      </div>
      <ul className="grid gap-1.5">
        {items.map((item: LabProbeResult) => (
          <li key={item.id} className="flex items-start gap-2 text-sm">
            {item.passed ? (
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-label={t("o'tdi")} />
            ) : (
              <CircleX className="mt-0.5 size-4 shrink-0 text-red-600" aria-label={t("o'tmadi")} />
            )}
            <div className="grid gap-0.5">
              <div className="flex flex-wrap items-center gap-2">
                <span>{item.title}</span>
                <KindBadge kind={item.kind} />
              </div>
              {item.message ? <span className="text-xs break-words text-muted-foreground">{item.message}</span> : null}
            </div>
          </li>
        ))}
      </ul>
      {result.hidden_probes?.total ? (
        <p className="text-xs text-muted-foreground">
          {t("Yashirin sinovlar: {passed} / {total} o'tdi.", { passed: result.hidden_probes.passed, total: result.hidden_probes.total })}
        </p>
      ) : null}
    </div>
  )
}

function newProbe(probes: LabProbe[]): LabProbe {
  let index = probes.length + 1
  while (probes.some((probe) => probe.id === `s${index}`)) index += 1
  return { id: `s${index}`, title: '', kind: 'attack', sql: '', hidden: false }
}

/** O'qituvchiga: sinovlar muharriri (saqlashda server har birini namunaviy yechim bilan tekshiradi) */
export function ProbesEditor({ value, onChange }: { value: LabProbe[]; onChange: (probes: LabProbe[]) => void }) {
  function update(index: number, patch: Partial<LabProbe>) {
    onChange(value.map((probe, position) => (position === index ? { ...probe, ...patch } : probe)))
  }

  return (
    <div className="grid gap-3">
      {value.map((probe, index) => (
        <fieldset key={probe.id} className="grid gap-2 rounded-lg border p-3">
          <legend className="sr-only">{t('{value}-sinov', { value: index + 1 })}</legend>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              aria-label={t('{value}-sinov nomi', { value: index + 1 })}
              className="min-w-48 flex-1"
              placeholder={t('masalan: Manfiy narx')}
              maxLength={200}
              value={probe.title}
              onChange={(event) => update(index, { title: event.target.value })}
            />
            <select
              aria-label={t('{value}-sinov turi', { value: index + 1 })}
              className="h-10 rounded-md border bg-background px-2 text-sm"
              value={probe.kind}
              onChange={(event) => update(index, { kind: event.target.value as LabProbe['kind'] })}
            >
              <option value="attack">{t('Hujum (rad etilsin)')}</option>
              <option value="valid">{t("To'g'ri ma'lumot (qabul qilinsin)")}</option>
            </select>
            <label className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={Boolean(probe.hidden)}
                onChange={(event) => update(index, { hidden: event.target.checked })}
              />
              {t('Yashirin')}
            </label>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={t("{value}-sinovni o'chirish", { value: index + 1 })}
              onClick={() => onChange(value.filter((_, position) => position !== index))}
            >
              <Trash2 aria-hidden="true" />
            </Button>
          </div>
          <Textarea
            aria-label={t("{value}-sinov SQL'i", { value: index + 1 })}
            className="max-h-40 min-h-14 font-mono text-sm md:text-xs"
            placeholder={t("INSERT INTO mahsulot VALUES (2, 'Daftar', -5, 1)")}
            maxLength={2000}
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            value={probe.sql}
            onChange={(event) => update(index, { sql: event.target.value })}
          />
        </fieldset>
      ))}
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="justify-self-start"
        disabled={value.length >= 20}
        onClick={() => onChange([...value, newProbe(value)])}
      >
        <Plus aria-hidden="true" />
        {t("Sinov qo'shish")}
      </Button>
    </div>
  )
}
