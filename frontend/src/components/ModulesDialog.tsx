import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Loader2, Plus, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormField } from '@/components/FormField'
import { LabLevelBadge } from '@/components/LabLevel'
import { ErrorState, ListSkeleton } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import type { Lab, LabModule } from '@/lib/types'
import { cn } from '@/lib/utils'
import { t } from '@/lib/i18n'

interface Draft {
  title: string
  description: string
  order: string
  sequential: boolean
  examStart: string
  examEnd: string
  labs: number[]
}

/** ISO vaqt -> <input type="datetime-local"> qiymati (brauzerning mahalliy vaqtida) */
function toLocalInput(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function fromLocalInput(value: string) {
  return value ? new Date(value).toISOString() : null
}

function draftOf(module: LabModule | null, nextOrder: number): Draft {
  return module
    ? {
        title: module.title,
        description: module.description,
        order: String(module.order),
        sequential: module.sequential,
        examStart: toLocalInput(module.exam_starts_at),
        examEnd: toLocalInput(module.exam_ends_at),
        labs: module.labs.map((lab) => lab.id),
      }
    : { title: '', description: '', order: String(nextOrder), sequential: true, examStart: '', examEnd: '', labs: [] }
}

function ModuleEditor({
  module,
  labs,
  nextOrder,
  onSaved,
  onDeleted,
}: {
  module: LabModule | null
  labs: Lab[]
  nextOrder: number
  onSaved: (module: LabModule) => void
  onDeleted: () => void
}) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft>(() => draftOf(module, nextOrder))
  const [adding, setAdding] = useState('')
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const byId = new Map(labs.map((lab) => [lab.id, lab]))

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['lab-modules'] })
    void queryClient.invalidateQueries({ queryKey: ['labs'] })
  }

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        title: draft.title.trim(),
        description: draft.description,
        order: Number(draft.order) || 0,
        sequential: draft.sequential,
        exam_starts_at: fromLocalInput(draft.examStart),
        exam_ends_at: fromLocalInput(draft.examEnd),
      }
      const saved = module
        ? await api<LabModule>(`/lab-modules/${module.id}/`, { method: 'PATCH', body })
        : await api<LabModule>('/lab-modules/', { method: 'POST', body })
      return api<LabModule>(`/lab-modules/${saved.id}/reorder/`, { method: 'POST', body: { labs: draft.labs } })
    },
    onSuccess: (saved) => {
      toast.success(t('Modul saqlandi'))
      invalidate()
      onSaved(saved)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  const remove = useMutation({
    mutationFn: () => api(`/lab-modules/${module!.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success(t("Modul o'chirildi. Laboratoriyalari o'chmadi, «Boshqa laboratoriyalar»ga o'tdi."))
      invalidate()
      onDeleted()
    },
    onError: (error) => {
      toast.error(errorMessage(error))
      setConfirmingDelete(false)
    },
  })

  function move(index: number, delta: number) {
    const next = [...draft.labs]
    const [item] = next.splice(index, 1)
    next.splice(index + delta, 0, item)
    setDraft({ ...draft, labs: next })
  }

  const available = labs.filter((lab) => !draft.labs.includes(lab.id))

  return (
    <div className="grid content-start gap-4">
      <FormField id="module_title" label={t('Modul nomi')}>
        <Input
          id="module_title"
          className="h-10"
          maxLength={200}
          placeholder={t('Masalan: 1-modul. ER-model')}
          value={draft.title}
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
        />
      </FormField>
      <FormField id="module_description" label={t('Izoh (ixtiyoriy)')}>
        <Textarea
          id="module_description"
          rows={2}
          maxLength={2000}
          value={draft.description}
          onChange={(event) => setDraft({ ...draft, description: event.target.value })}
        />
      </FormField>
      <div className="flex flex-wrap items-end gap-4">
        <FormField id="module_order" label={t('Modul tartibi')} hint={t('Kichigi oldin turadi')}>
          <Input
            id="module_order"
            type="number"
            min={0}
            className="h-10 w-28"
            value={draft.order}
            onChange={(event) => setDraft({ ...draft, order: event.target.value })}
          />
        </FormField>
        <label className="flex items-center gap-2 pb-2.5 text-sm">
          <Checkbox
            checked={draft.sequential}
            onCheckedChange={(checked) => setDraft({ ...draft, sequential: checked === true })}
          />
          {t('Ketma-ket: oldingi laboratoriya yechilmaguncha keyingisi yopiq')}
        </label>
      </div>

      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">{t('Imtihon rejimi (ixtiyoriy)')}</legend>
        <div className="flex flex-wrap items-end gap-4">
          <FormField id="module_exam_start" label={t('Boshlanishi')}>
            <Input
              id="module_exam_start"
              type="datetime-local"
              className="h-10"
              value={draft.examStart}
              onChange={(event) => setDraft({ ...draft, examStart: event.target.value })}
            />
          </FormField>
          <FormField id="module_exam_end" label={t('Tugashi')}>
            <Input
              id="module_exam_end"
              type="datetime-local"
              className="h-10"
              value={draft.examEnd}
              onChange={(event) => setDraft({ ...draft, examEnd: event.target.value })}
            />
          </FormField>
          {draft.examStart || draft.examEnd ? (
            <Button type="button" variant="ghost" size="lg" onClick={() => setDraft({ ...draft, examStart: '', examEnd: '' })}>
              {t('Imtihonni bekor qilish')}
            </Button>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">
          {t("Boshlanishidan oldin laboratoriyalar talabalarga yopiq; imtihon paytida AI yordami, murabbiy va o'zaro baholash o'chiriladi, ball avtomatik qo'yiladi; tugagach yechimni faqat ko'rish mumkin.")}
        </p>
      </fieldset>

      <div className="grid gap-2">
        <div className="text-sm font-medium">{t('Laboratoriyalar (soddadan murakkabga)')}</div>
        {draft.labs.length ? (
          <ol className="grid gap-1.5">
            {draft.labs.map((id, index) => {
              const lab = byId.get(id)
              return (
                <li key={id} className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm">
                  <span className="w-6 text-muted-foreground tabular-nums">{index + 1}.</span>
                  <span className="min-w-0 flex-1 truncate" title={lab?.title}>
                    {lab?.title ?? `#${id}`}
                  </span>
                  {lab?.level ? <LabLevelBadge level={lab.level} /> : null}
                  <Button type="button" variant="ghost" size="icon" aria-label={t('Yuqoriga')} disabled={index === 0} onClick={() => move(index, -1)}>
                    <ArrowUp />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={t('Pastga')}
                    disabled={index === draft.labs.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    <ArrowDown />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={t('Moduldan chiqarish')}
                    onClick={() => setDraft({ ...draft, labs: draft.labs.filter((item) => item !== id) })}
                  >
                    <X />
                  </Button>
                </li>
              )
            })}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">{t("Modulda hali laboratoriya yo'q.")}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label={t("Qo'shiladigan laboratoriya")}
            className="h-10 min-w-0 flex-1 rounded-md border bg-background px-2 text-sm"
            value={adding}
            onChange={(event) => setAdding(event.target.value)}
          >
            <option value="">{t('Laboratoriyani tanlang…')}</option>
            {available.map((lab) => (
              <option key={lab.id} value={lab.id}>
                {lab.title}
                {lab.level ? t(' (murakkablik {level})', { level: lab.level }) : ''}
                {lab.module_detail ? t(' — hozir «{title}» modulida', { title: lab.module_detail.title }) : ''}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="outline"
            size="lg"
            disabled={!adding}
            onClick={() => {
              setDraft({ ...draft, labs: [...draft.labs, Number(adding)] })
              setAdding('')
            }}
          >
            <Plus aria-hidden="true" />
            {t("Qo'shish")}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
        {module ? (
          <Button type="button" variant="destructive" size="lg" onClick={() => setConfirmingDelete(true)}>
            <Trash2 aria-hidden="true" />
            {t("O'chirish")}
          </Button>
        ) : (
          <span />
        )}
        <Button type="button" size="lg" disabled={save.isPending || !draft.title.trim()} onClick={() => save.mutate()}>
          {save.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
          {t('Saqlash')}
        </Button>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        title={t("Modulni o'chirish")}
        description={t("«{title}» o'chiriladi. Laboratoriyalar va talabalar natijalari saqlanadi.", { title: module?.title ?? '' })}
        confirmLabel={t("O'chirish")}
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirmingDelete(false)}
      />
    </div>
  )
}

/** Modullar: yaratish, tartiblash va laboratoriyalarni soddadan murakkabga joylash (admin va o'qituvchi) */
export function ModulesDialog({ labs, onClose }: { labs: Lab[]; onClose: () => void }) {
  const modules = useQuery({ queryKey: ['lab-modules'], queryFn: () => api<LabModule[]>('/lab-modules/') })
  // null — yangi modul
  const [selected, setSelected] = useState<number | null | undefined>(undefined)

  const list = modules.data ?? []
  const current = selected === undefined ? (list[0] ?? null) : selected === null ? null : (list.find((item) => item.id === selected) ?? null)
  const nextOrder = list.length ? Math.max(...list.map((item) => item.order)) + 1 : 1

  let content
  if (modules.isPending) content = <ListSkeleton rows={2} />
  else if (modules.isError) content = <ErrorState error={modules.error} onRetry={() => void modules.refetch()} />
  else
    content = (
      <div className="grid gap-4 md:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label={t('Modullar')} className="grid content-start gap-1">
          {list.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelected(item.id)}
              className={cn(
                'rounded-lg px-3 py-2 text-left text-sm transition-colors',
                current?.id === item.id ? 'bg-primary/10 font-medium text-primary' : 'hover:bg-muted',
              )}
            >
              <span className="block truncate">{item.title}</span>
              <span className="text-xs text-muted-foreground">{t('{length} ta laboratoriya', { length: item.labs.length })}</span>
            </button>
          ))}
          <Button type="button" variant="outline" size="lg" className="mt-1 justify-start" onClick={() => setSelected(null)}>
            <Plus aria-hidden="true" />
            {t('Yangi modul')}
          </Button>
        </nav>
        {/* Modul tanlanmagan yoki hali yo'q bo'lsa — yangi modul formasi */}
        <ModuleEditor
          key={current?.id ?? 'new'}
          module={current}
          labs={labs}
          nextOrder={nextOrder}
          onSaved={(saved) => setSelected(saved.id)}
          onDeleted={() => setSelected(undefined)}
        />
      </div>
    )

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{t('Laboratoriyalar modullari')}</DialogTitle>
          <DialogDescription>
            {t("Laboratoriyalarni modullarga ajrating va soddadan murakkabga tartiblang. Ketma-ket modulda talaba oldingi laboratoriyani yechmaguncha keyingisi ochilmaydi; modullar ham tartib bo'yicha bir-biridan keyin ochiladi.")}
          </DialogDescription>
        </DialogHeader>
        {content}
        <DialogFooter>
          <Button variant="outline" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
