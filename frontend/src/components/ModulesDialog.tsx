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

interface Draft {
  title: string
  description: string
  order: string
  sequential: boolean
  labs: number[]
}

function draftOf(module: LabModule | null, nextOrder: number): Draft {
  return module
    ? {
        title: module.title,
        description: module.description,
        order: String(module.order),
        sequential: module.sequential,
        labs: module.labs.map((lab) => lab.id),
      }
    : { title: '', description: '', order: String(nextOrder), sequential: true, labs: [] }
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
      }
      const saved = module
        ? await api<LabModule>(`/lab-modules/${module.id}/`, { method: 'PATCH', body })
        : await api<LabModule>('/lab-modules/', { method: 'POST', body })
      return api<LabModule>(`/lab-modules/${saved.id}/reorder/`, { method: 'POST', body: { labs: draft.labs } })
    },
    onSuccess: (saved) => {
      toast.success('Modul saqlandi')
      invalidate()
      onSaved(saved)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  const remove = useMutation({
    mutationFn: () => api(`/lab-modules/${module!.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success("Modul o'chirildi. Laboratoriyalari o'chmadi, «Boshqa laboratoriyalar»ga o'tdi.")
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
      <FormField id="module_title" label="Modul nomi">
        <Input
          id="module_title"
          className="h-10"
          maxLength={200}
          placeholder="Masalan: 1-modul. ER-model"
          value={draft.title}
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
        />
      </FormField>
      <FormField id="module_description" label="Izoh (ixtiyoriy)">
        <Textarea
          id="module_description"
          rows={2}
          maxLength={2000}
          value={draft.description}
          onChange={(event) => setDraft({ ...draft, description: event.target.value })}
        />
      </FormField>
      <div className="flex flex-wrap items-end gap-4">
        <FormField id="module_order" label="Modul tartibi" hint="Kichigi oldin turadi">
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
          Ketma-ket: oldingi laboratoriya yechilmaguncha keyingisi yopiq
        </label>
      </div>

      <div className="grid gap-2">
        <div className="text-sm font-medium">Laboratoriyalar (soddadan murakkabga)</div>
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
                  <Button type="button" variant="ghost" size="icon" aria-label="Yuqoriga" disabled={index === 0} onClick={() => move(index, -1)}>
                    <ArrowUp />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="Pastga"
                    disabled={index === draft.labs.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    <ArrowDown />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="Moduldan chiqarish"
                    onClick={() => setDraft({ ...draft, labs: draft.labs.filter((item) => item !== id) })}
                  >
                    <X />
                  </Button>
                </li>
              )
            })}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">Modulda hali laboratoriya yo'q.</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Qo'shiladigan laboratoriya"
            className="h-10 min-w-0 flex-1 rounded-md border bg-background px-2 text-sm"
            value={adding}
            onChange={(event) => setAdding(event.target.value)}
          >
            <option value="">Laboratoriyani tanlang…</option>
            {available.map((lab) => (
              <option key={lab.id} value={lab.id}>
                {lab.title}
                {lab.level ? ` (murakkablik ${lab.level})` : ''}
                {lab.module_detail ? ` — hozir «${lab.module_detail.title}» modulida` : ''}
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
            Qo'shish
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
        {module ? (
          <Button type="button" variant="destructive" size="lg" onClick={() => setConfirmingDelete(true)}>
            <Trash2 aria-hidden="true" />
            O'chirish
          </Button>
        ) : (
          <span />
        )}
        <Button type="button" size="lg" disabled={save.isPending || !draft.title.trim()} onClick={() => save.mutate()}>
          {save.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
          Saqlash
        </Button>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        title="Modulni o'chirish"
        description={`«${module?.title ?? ''}» o'chiriladi. Laboratoriyalar va talabalar natijalari saqlanadi.`}
        confirmLabel="O'chirish"
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
        <nav aria-label="Modullar" className="grid content-start gap-1">
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
              <span className="text-xs text-muted-foreground">{item.labs.length} ta laboratoriya</span>
            </button>
          ))}
          <Button type="button" variant="outline" size="lg" className="mt-1 justify-start" onClick={() => setSelected(null)}>
            <Plus aria-hidden="true" />
            Yangi modul
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
          <DialogTitle>Laboratoriyalar modullari</DialogTitle>
          <DialogDescription>
            Laboratoriyalarni modullarga ajrating va soddadan murakkabga tartiblang. Ketma-ket modulda talaba oldingi
            laboratoriyani yechmaguncha keyingisi ochilmaydi; modullar ham tartib bo'yicha bir-biridan keyin ochiladi.
          </DialogDescription>
        </DialogHeader>
        {content}
        <DialogFooter>
          <Button variant="outline" size="lg" onClick={onClose}>
            Yopish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
