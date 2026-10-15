import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { CheckList } from '@/components/CheckList'
import { FormField } from '@/components/FormField'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'
import { applyFormError } from '@/lib/forms'
import { useGroupOptions } from '@/lib/groups'
import type { Lab } from '@/lib/types'

const LAB_FIELDS = ['title', 'description', 'setup_sql', 'solution_sql', 'groups'] as const
const SQL_PROPS = { spellCheck: false, autoCapitalize: 'none', autoCorrect: 'off' } as const

interface LabDialogProps {
  /** Berilmasa — yangi laboratoriya yaratiladi */
  lab?: Lab
  onClose: () => void
}

export function LabDialog({ lab, onClose }: LabDialogProps) {
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()

  const [title, setTitle] = useState(lab?.title ?? '')
  const [description, setDescription] = useState(lab?.description ?? '')
  const [setupSql, setSetupSql] = useState(lab?.setup_sql ?? '')
  const [solutionSql, setSolutionSql] = useState(lab?.solution_sql ?? '')
  const [groupIds, setGroupIds] = useState<number[]>(lab?.groups ?? [])
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () => {
      const body = {
        title: title.trim(),
        description,
        setup_sql: setupSql,
        solution_sql: solutionSql,
        groups: groupIds,
      }
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
    setErrors(problems)
    if (!Object.keys(problems).length) mutation.mutate()
  }

  return (
    <Dialog open onOpenChange={(open) => (!open && !mutation.isPending ? onClose() : undefined)}>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{lab ? 'Laboratoriyani tahrirlash' : 'Yangi laboratoriya'}</DialogTitle>
          <DialogDescription>
            Talaba SQL kod yozib ishga tushiradi; tizim natijani namunaviy yechim bilan solishtiradi.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
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
            hint="Jadval va ustun nomlarini aniq yozing: talaba natijasi namuna bilan solishtiriladi."
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
              {mutation.isPending ? 'Kod tekshirilmoqda…' : 'Saqlash'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
