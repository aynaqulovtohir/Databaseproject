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
import { toLocalInputValue } from '@/lib/format'
import { useGroupOptions } from '@/lib/groups'
import type { Assignment } from '@/lib/types'

const ASSIGNMENT_FIELDS = ['title', 'description', 'grading_criteria', 'groups', 'deadline'] as const

interface AssignmentDialogProps {
  /** Berilmasa — yangi topshiriq yaratiladi */
  assignment?: Assignment
  onClose: () => void
}

export function AssignmentDialog({ assignment, onClose }: AssignmentDialogProps) {
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()
  const initialDeadline = assignment ? toLocalInputValue(assignment.deadline) : ''

  const [title, setTitle] = useState(assignment?.title ?? '')
  const [description, setDescription] = useState(assignment?.description ?? '')
  const [criteria, setCriteria] = useState(assignment?.grading_criteria ?? '')
  const [groupIds, setGroupIds] = useState<number[]>(assignment?.groups ?? [])
  const [deadline, setDeadline] = useState(initialDeadline)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        title: title.trim(),
        description,
        grading_criteria: criteria,
        groups: groupIds,
      }
      // Muddat o'zgartirilmagan bo'lsa yuborilmaydi: o'tib ketgan muddatli
      // topshiriqning boshqa maydonlarini tahrirlash mumkin bo'lishi kerak
      if (deadline !== initialDeadline) body.deadline = new Date(deadline).toISOString()
      return assignment
        ? api<Assignment>(`/assignments/${assignment.id}/`, { method: 'PATCH', body })
        : api<Assignment>('/assignments/', { method: 'POST', body })
    },
    onSuccess: (saved) => {
      toast.success(assignment ? 'Topshiriq saqlandi' : 'Topshiriq yaratildi')
      queryClient.setQueryData(['assignment', saved.id], saved)
      void queryClient.invalidateQueries({ queryKey: ['assignments'] })
      onClose()
    },
    onError: (error) => applyFormError(error, ASSIGNMENT_FIELDS, setErrors),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const problems: Record<string, string> = {}
    if (!groupIds.length) problems.groups = 'Kamida bitta guruh tanlang.'
    if (!deadline || Number.isNaN(new Date(deadline).getTime())) problems.deadline = 'Muddatni kiriting.'
    setErrors(problems)
    if (!Object.keys(problems).length) mutation.mutate()
  }

  return (
    <Dialog open onOpenChange={(open) => (!open && !mutation.isPending ? onClose() : undefined)}>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{assignment ? 'Topshiriqni tahrirlash' : 'Yangi topshiriq'}</DialogTitle>
          <DialogDescription>Talabalar yechimni SQL kod ko'rinishida topshiradi.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          <FormField id="assignment_title" label="Sarlavha" error={errors.title}>
            <Input
              id="assignment_title"
              className="h-10"
              aria-invalid={Boolean(errors.title)}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </FormField>
          <FormField id="assignment_description" label="Topshiriq sharti" error={errors.description}>
            <Textarea
              id="assignment_description"
              className="max-h-64 min-h-28"
              aria-invalid={Boolean(errors.description)}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </FormField>
          <FormField
            id="assignment_criteria"
            label="Baholash mezonlari"
            error={errors.grading_criteria}
            hint="Ixtiyoriy. Talabaga ko'rinmaydi; AI tahlilida va ball taklif qilishda ishlatiladi."
          >
            <Textarea
              id="assignment_criteria"
              className="max-h-48 min-h-20"
              aria-invalid={Boolean(errors.grading_criteria)}
              value={criteria}
              onChange={(event) => setCriteria(event.target.value)}
            />
          </FormField>
          <FormField id="assignment_groups" label="Guruhlar" error={errors.groups}>
            <CheckList
              idPrefix="assignment-group"
              options={groups.map((group) => ({ id: group.id, label: group.name }))}
              selected={groupIds}
              onChange={setGroupIds}
              emptyText="Sizga hali guruh biriktirilmagan. Administratorga murojaat qiling."
              invalid={Boolean(errors.groups)}
            />
          </FormField>
          <FormField
            id="assignment_deadline"
            label="Muddat"
            error={errors.deadline}
            hint="Muddatdan keyin topshirilgan yechim «kechikkan» deb belgilanadi."
          >
            <Input
              id="assignment_deadline"
              type="datetime-local"
              className="h-10 w-full sm:w-64"
              aria-invalid={Boolean(errors.deadline)}
              value={deadline}
              onChange={(event) => setDeadline(event.target.value)}
            />
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" disabled={mutation.isPending} onClick={onClose}>
              Bekor qilish
            </Button>
            <Button type="submit" size="lg" disabled={mutation.isPending || !title.trim() || !description.trim()}>
              {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              Saqlash
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
