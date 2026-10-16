import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { CheckList } from '@/components/CheckList'
import { ErEditor } from '@/components/ErEditor'
import { FormField } from '@/components/FormField'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { cleanDiagram, EMPTY_DIAGRAM } from '@/lib/er'
import { applyFormError } from '@/lib/forms'
import { useGroupOptions } from '@/lib/groups'
import { cn } from '@/lib/utils'
import type { ErDiagram, Lab, LabKind } from '@/lib/types'

const LAB_FIELDS = ['kind', 'title', 'description', 'theory', 'setup_sql', 'solution_sql', 'reference_diagram', 'groups'] as const

const KIND_OPTIONS: { value: LabKind; label: string; hint: string }[] = [
  { value: 'sql', label: 'SQL kod', hint: 'Talaba SQL yozadi, natija namunaviy yechim bilan solishtiriladi.' },
  { value: 'er', label: 'ER-diagramma', hint: 'Talaba ER-diagramma chizadi, u namunaviy diagramma bilan solishtiriladi.' },
]
const SQL_PROPS = { spellCheck: false, autoCapitalize: 'none', autoCorrect: 'off' } as const

interface LabDialogProps {
  /** Berilmasa — yangi laboratoriya yaratiladi */
  lab?: Lab
  onClose: () => void
}

export function LabDialog({ lab, onClose }: LabDialogProps) {
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()

  const [kind, setKind] = useState<LabKind>(lab?.kind ?? 'sql')
  const [referenceDiagram, setReferenceDiagram] = useState<ErDiagram>(lab?.reference_diagram ?? EMPTY_DIAGRAM)
  const [title, setTitle] = useState(lab?.title ?? '')
  const [description, setDescription] = useState(lab?.description ?? '')
  const [theory, setTheory] = useState(lab?.theory ?? '')
  const [setupSql, setSetupSql] = useState(lab?.setup_sql ?? '')
  const [solutionSql, setSolutionSql] = useState(lab?.solution_sql ?? '')
  const [groupIds, setGroupIds] = useState<number[]>(lab?.groups ?? [])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () => {
      const common = { title: title.trim(), description, theory, groups: groupIds }
      const body =
        kind === 'er'
          ? { ...common, kind, reference_diagram: cleanDiagram(referenceDiagram) }
          : { ...common, kind, setup_sql: setupSql, solution_sql: solutionSql }
      return lab
        ? api<Lab>(`/labs/${lab.id}/`, { method: 'PATCH', body })
        : api<Lab>('/labs/', { method: 'POST', body })
    },
    onSuccess: (saved) => {
      toast.success(lab ? 'Laboratoriya saqlandi' : 'Laboratoriya yaratildi')
      queryClient.setQueryData(['lab', saved.id], saved)
      void queryClient.invalidateQueries({ queryKey: ['labs'] })
      onClose()
    },
    onError: (error) => applyFormError(error, LAB_FIELDS, setErrors),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const problems: Record<string, string> = {}
    if (!groupIds.length) problems.groups = 'Kamida bitta guruh tanlang.'
    if (kind === 'er' && !referenceDiagram.entities.length) {
      problems.reference_diagram = 'Namunaviy diagrammada kamida bitta obyekt chizing.'
    }
    setErrors(problems)
    if (!Object.keys(problems).length) mutation.mutate()
  }

  return (
    <Dialog open onOpenChange={(open) => (!open && !mutation.isPending ? onClose() : undefined)}>
      <DialogContent className={cn('max-h-[92svh] overflow-y-auto', kind === 'er' ? 'sm:max-w-6xl' : 'sm:max-w-2xl')}>
        <DialogHeader>
          <DialogTitle>{lab ? 'Laboratoriyani tahrirlash' : 'Yangi laboratoriya'}</DialogTitle>
          <DialogDescription>{KIND_OPTIONS.find((option) => option.value === kind)?.hint}</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          {lab ? null : (
            <fieldset className="grid gap-1.5">
              <legend className="mb-1.5 text-sm font-medium">Laboratoriya turi</legend>
              <div className="flex flex-wrap gap-2">
                {KIND_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={cn(
                      'flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm',
                      kind === option.value && 'border-primary bg-primary/5',
                    )}
                  >
                    <input
                      type="radio"
                      name="lab_kind"
                      value={option.value}
                      checked={kind === option.value}
                      onChange={() => setKind(option.value)}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <FormField id="lab_title" label="Sarlavha" error={errors.title}>
            <Input
              id="lab_title"
              className="h-10"
              aria-invalid={Boolean(errors.title)}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </FormField>
          <FormField
            id="lab_description"
            label="Laboratoriya sharti"
            error={errors.description}
            hint={
              kind === 'er'
                ? "Obyekt va atribut nomlarini aniq yozing: talaba diagrammasi nomlar bo'yicha solishtiriladi."
                : 'Jadval va ustun nomlarini aniq yozing: talaba natijasi namuna bilan solishtiriladi.'
            }
          >
            <Textarea
              id="lab_description"
              className="max-h-64 min-h-24"
              aria-invalid={Boolean(errors.description)}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </FormField>
          <FormField
            id="lab_theory"
            label="Nazariya va namuna (ixtiyoriy)"
            error={errors.theory}
            hint="Talabaga shart ostida ko'rinadi. Kodni ``` qatorlari orasiga yozing. Namunani boshqa mavzuda bering, yechimni yozmang."
          >
            <Textarea
              id="lab_theory"
              className="max-h-64 min-h-24"
              maxLength={20000}
              aria-invalid={Boolean(errors.theory)}
              value={theory}
              onChange={(event) => setTheory(event.target.value)}
            />
          </FormField>
          {kind === 'er' ? (
            <div className="grid gap-1.5">
              <span className="text-sm font-medium">Namunaviy ER-diagramma</span>
              <p className="text-xs text-muted-foreground">
                Talabaga ko'rinmaydi. Talaba diagrammasi shu bilan solishtiriladi: obyektlar, atributlar, PK va
                bog'lanishlar kardinalligi. FK atributlari solishtirilmaydi.
              </p>
              <ErEditor value={referenceDiagram} onChange={setReferenceDiagram} />
              {errors.reference_diagram ? (
                <p className="text-xs text-destructive" role="alert">
                  {errors.reference_diagram}
                </p>
              ) : null}
            </div>
          ) : (
            <>
              <FormField
                id="lab_setup"
                label="Tayyor jadvallar (SQL)"
                error={errors.setup_sql}
                hint="Ixtiyoriy. Talaba kodidan oldin bajariladi va talabaga ko'rinadi: CREATE TABLE va INSERT buyruqlari."
              >
                <Textarea
                  id="lab_setup"
                  className="max-h-64 min-h-28 font-mono text-sm md:text-xs"
                  placeholder={"CREATE TABLE kitob (id INT PRIMARY KEY, nomi VARCHAR(100));\nINSERT INTO kitob VALUES (1, 'Alifbo');"}
                  aria-invalid={Boolean(errors.setup_sql)}
                  value={setupSql}
                  onChange={(event) => setSetupSql(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
              <FormField
                id="lab_solution"
                label="Namunaviy yechim (SQL)"
                error={errors.solution_sql}
                hint="Talabaga ko'rinmaydi. Bo'sh qoldirilsa, xatosiz ishlagan har qanday kod to'g'ri hisoblanadi."
              >
                <Textarea
                  id="lab_solution"
                  className="max-h-64 min-h-28 font-mono text-sm md:text-xs"
                  placeholder="SELECT nomi FROM kitob ORDER BY nomi;"
                  aria-invalid={Boolean(errors.solution_sql)}
                  value={solutionSql}
                  onChange={(event) => setSolutionSql(event.target.value)}
                  {...SQL_PROPS}
                />
              </FormField>
            </>
          )}
          <FormField id="lab_groups" label="Guruhlar" error={errors.groups}>
            <CheckList
              idPrefix="lab-group"
              options={groups.map((group) => ({ id: group.id, label: group.name }))}
              selected={groupIds}
              onChange={setGroupIds}
              emptyText="Sizga hali guruh biriktirilmagan. Administratorga murojaat qiling."
              invalid={Boolean(errors.groups)}
            />
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" disabled={mutation.isPending} onClick={onClose}>
              Bekor qilish
            </Button>
            <Button type="submit" size="lg" disabled={mutation.isPending || !title.trim() || !description.trim()}>
              {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              {mutation.isPending ? (kind === 'er' ? 'Saqlanmoqda…' : 'Kod tekshirilmoqda…') : 'Saqlash'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
