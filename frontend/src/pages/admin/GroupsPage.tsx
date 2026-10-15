import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Pencil, Plus, Trash2, UsersRound } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { CheckList } from '@/components/CheckList'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormField } from '@/components/FormField'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { fullName } from '@/lib/auth'
import { applyFormError } from '@/lib/forms'
import type { AdminUser, Group } from '@/lib/types'

const GROUP_FIELDS = ['name', 'teachers', 'ai_enabled'] as const

interface GroupDialogProps {
  group?: Group
  teachers: AdminUser[]
  onClose: () => void
}

function GroupDialog({ group, teachers, onClose }: GroupDialogProps) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(group?.name ?? '')
  const [teacherIds, setTeacherIds] = useState<number[]>(group?.teachers ?? [])
  const [aiEnabled, setAiEnabled] = useState(group?.ai_enabled ?? true)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), teachers: teacherIds, ai_enabled: aiEnabled }
      return group
        ? api<Group>(`/groups/${group.id}/`, { method: 'PATCH', body })
        : api<Group>('/groups/', { method: 'POST', body })
    },
    onSuccess: () => {
      toast.success(group ? 'Guruh saqlandi' : 'Guruh yaratildi')
      void queryClient.invalidateQueries({ queryKey: ['groups'] })
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (error) => applyFormError(error, GROUP_FIELDS, setErrors),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setErrors({})
    mutation.mutate()
  }

  return (
    <Dialog open onOpenChange={(open) => (!open && !mutation.isPending ? onClose() : undefined)}>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{group ? 'Guruhni tahrirlash' : 'Yangi guruh'}</DialogTitle>
          <DialogDescription>
            Biriktirilgan o'qituvchilar shu guruhga material va topshiriq bera oladi.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          <FormField id="group_name" label="Guruh nomi" error={errors.name}>
            <Input
              id="group_name"
              className="h-10"
              placeholder="Masalan: 210-21"
              aria-invalid={Boolean(errors.name)}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </FormField>
          <FormField id="group_teachers" label="O'qituvchilar" error={errors.teachers}>
            <CheckList
              idPrefix="teacher"
              options={teachers.map((teacher) => ({ id: teacher.id, label: fullName(teacher) }))}
              selected={teacherIds}
              onChange={setTeacherIds}
              emptyText="Hali o'qituvchi yo'q. Avval «Foydalanuvchilar» sahifasida o'qituvchi yarating."
              invalid={Boolean(errors.teachers)}
            />
          </FormField>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 size-4"
              checked={aiEnabled}
              onChange={(event) => setAiEnabled(event.target.checked)}
            />
            <span>
              AI yordamchisi yoqilgan
              <span className="block text-xs text-muted-foreground">
                Tajriba uchun nazorat guruhida o'chiring: talabalar AI maslahati, AI bahosi, AI chat va AI tahlilini
                ko'rmaydi (baho avtomatik tekshiruv bilan qo'yiladi). O'qituvchiga AI tahlili ko'rinaveradi.
              </span>
            </span>
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" disabled={mutation.isPending} onClick={onClose}>
              Bekor qilish
            </Button>
            <Button type="submit" size="lg" disabled={mutation.isPending || !name.trim()}>
              {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              Saqlash
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function GroupsPage() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Group | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Group | null>(null)

  const groups = useQuery({ queryKey: ['groups'], queryFn: () => api<Group[]>('/groups/') })
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<AdminUser[]>('/users/') })
  const teachers = useMemo(
    () => (users.data ?? []).filter((user) => user.role === 'teacher' && user.is_active),
    [users.data],
  )

  const remove = useMutation({
    mutationFn: (group: Group) => api(`/groups/${group.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success("Guruh o'chirildi")
      void queryClient.invalidateQueries({ queryKey: ['groups'] })
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      setDeleting(null)
    },
    onError: (error) => {
      toast.error(errorMessage(error))
      setDeleting(null)
    },
  })

  function teacherNames(ids: number[]): string {
    if (!ids.length) return '—'
    return ids
      .map((id) => {
        const teacher = users.data?.find((user) => user.id === id)
        return teacher ? fullName(teacher) : `#${id}`
      })
      .join(', ')
  }

  const addButton = (
    <Button size="lg" onClick={() => setEditing('new')}>
      <Plus aria-hidden="true" />
      Guruh qo'shish
    </Button>
  )

  let content
  if (groups.isPending) {
    content = <ListSkeleton />
  } else if (groups.isError) {
    content = <ErrorState error={groups.error} onRetry={() => void groups.refetch()} />
  } else if (!groups.data.length) {
    content = (
      <EmptyState
        icon={UsersRound}
        title="Hali guruh yo'q"
        description="Talabalarni biriktirish uchun avval guruh yarating."
        action={addButton}
      />
    )
  } else {
    content = (
      <Card className="py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Guruh</TableHead>
              <TableHead>O'qituvchilar</TableHead>
              <TableHead>AI</TableHead>
              <TableHead className="text-right">Talabalar</TableHead>
              <TableHead className="text-right">Amallar</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.data.map((group) => (
              <TableRow key={group.id}>
                <TableCell className="font-medium">{group.name}</TableCell>
                <TableCell className="max-w-80 truncate">{teacherNames(group.teachers)}</TableCell>
                <TableCell>
                  {group.ai_enabled ? (
                    <Badge variant="outline">Yoqilgan</Badge>
                  ) : (
                    <Badge className="bg-amber-100 text-amber-800">O'chirilgan</Badge>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">{group.student_count}</TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      aria-label={`${group.name}: tahrirlash`}
                      onClick={() => setEditing(group)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      aria-label={`${group.name}: o'chirish`}
                      onClick={() => setDeleting(group)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    )
  }

  return (
    <>
      <PageHeader
        title="Guruhlar"
        description="Guruhlar va ularga biriktirilgan o'qituvchilar."
        actions={groups.data?.length ? addButton : null}
      />
      {content}

      {editing ? (
        <GroupDialog
          key={editing === 'new' ? 'new' : editing.id}
          group={editing === 'new' ? undefined : editing}
          teachers={teachers}
          onClose={() => setEditing(null)}
        />
      ) : null}
      <ConfirmDialog
        open={Boolean(deleting)}
        title="Guruhni o'chirish"
        description={
          deleting
            ? `«${deleting.name}» guruhi o'chiriladi. Undagi ${deleting.student_count} ta talaba guruhsiz qoladi va shu guruhga berilgan material hamda topshiriqlarni ko'rmay qoladi.`
            : ''
        }
        confirmLabel="O'chirish"
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
        onClose={() => setDeleting(null)}
      />
    </>
  )
}
