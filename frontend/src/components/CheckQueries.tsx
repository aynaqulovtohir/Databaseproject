import { CircleCheck, CircleX, Plus, Trash2 } from 'lucide-react'

import { SqlCode } from '@/components/SqlCode'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { LabCheckQuery, LabRunResult } from '@/lib/types'
import { t } from '@/lib/i18n'

/** Talabaga laboratoriya shartida: migratsiyadan keyin ilova bajaradigan so'rovlar */
export function CheckQueryList({ queries }: { queries: LabCheckQuery[] }) {
  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        {t("Kodingizdan keyin shu so'rovlar bajariladi (har biri alohida, keyin orqaga qaytariladi): ular xatosiz ishlashi va to'g'ri natija berishi kerak. Mavjud ma'lumotlar yo'qolmasin — tekshiruv boshqa (yashirin) ma'lumotlarda ham takrorlanadi.")}
      </p>
      <ul className="grid gap-3">
        {queries.map((query) => (
          <li key={query.id} className="grid gap-1.5">
            <span className="text-sm font-medium">{query.title}</span>
            <SqlCode code={query.sql} />
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Tekshiruv natijasi: har bir yangi so'rov o'tdimi */
export function CheckQueryResults({ result }: { result: LabRunResult }) {
  const items = result.queries ?? []
  if (!items.length) return null
  return (
    <div className="grid gap-2 rounded-lg border p-3">
      <div className="text-sm font-medium">
        {t("Tekshiruv so'rovlari: {length} / {items} ishladi", { length: items.filter((item) => item.passed).length, items: items.length })}
      </div>
      <ul className="grid gap-1.5">
        {items.map((item) => (
          <li key={item.id} className="flex items-start gap-2 text-sm">
            {item.passed ? (
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-label="ishladi" />
            ) : (
              <CircleX className="mt-0.5 size-4 shrink-0 text-red-600" aria-label="ishlamadi" />
            )}
            <div className="grid gap-0.5">
              <span>{item.title}</span>
              {item.message ? <span className="text-xs break-words text-muted-foreground">{item.message}</span> : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function newQuery(queries: LabCheckQuery[]): LabCheckQuery {
  let index = queries.length + 1
  while (queries.some((query) => query.id === `q${index}`)) index += 1
  return { id: `q${index}`, title: '', sql: '' }
}

/** O'qituvchiga: so'rovlar muharriri (saqlashda server namunaviy migratsiya bilan tekshiradi) */
export function CheckQueriesEditor({ value, onChange }: { value: LabCheckQuery[]; onChange: (queries: LabCheckQuery[]) => void }) {
  function update(index: number, patch: Partial<LabCheckQuery>) {
    onChange(value.map((query, position) => (position === index ? { ...query, ...patch } : query)))
  }

  return (
    <div className="grid gap-3">
      {value.map((query, index) => (
        <fieldset key={query.id} className="grid gap-2 rounded-lg border p-3">
          <legend className="sr-only">{t("{value}-so'rov", { value: index + 1 })}</legend>
          <div className="flex items-center gap-2">
            <Input
              aria-label={t("{value}-so'rov nomi", { value: index + 1 })}
              className="flex-1"
              placeholder={t("masalan: Familiya bo'yicha qidiruv")}
              maxLength={200}
              value={query.title}
              onChange={(event) => update(index, { title: event.target.value })}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={t("{value}-so'rovni o'chirish", { value: index + 1 })}
              onClick={() => onChange(value.filter((_, position) => position !== index))}
            >
              <Trash2 aria-hidden="true" />
            </Button>
          </div>
          <Textarea
            aria-label={t("{value}-so'rov SQL'i", { value: index + 1 })}
            className="max-h-40 min-h-14 font-mono text-sm md:text-xs"
            placeholder={t('SELECT ism, familiya FROM mijoz ORDER BY id')}
            maxLength={2000}
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            value={query.sql}
            onChange={(event) => update(index, { sql: event.target.value })}
          />
        </fieldset>
      ))}
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="justify-self-start"
        disabled={value.length >= 10}
        onClick={() => onChange([...value, newQuery(value)])}
      >
        <Plus aria-hidden="true" />
        {t("So'rov qo'shish")}
      </Button>
    </div>
  )
}
