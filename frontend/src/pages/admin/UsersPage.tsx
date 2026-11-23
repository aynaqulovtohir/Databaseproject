import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Pencil, Plus, Trash2, Users } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormField } from '@/components/FormField'
import { PasswordInput } from '@/components/PasswordInput'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { applyFormError } from '@/lib/forms'
import { groupNames } from '@/lib/groups'
import { ROLE_LABELS, type AdminUser, type Group, type Role } from '@/lib/types'
import { t } from '@/lib/i18n'

const NO_GROUP = 'none'
const USER_FIELDS = ['username', 'first_name', 'last_name', 'role', 'group', 'password', 'is_active'] as const

interface UserDialogProps {
  /** Berilmasa — yangi foydalanuvchi yaratiladi */
  user?: AdminUser
  groups: Group[]
  onClose: () => void
}

function UserDialog({ user, groups, onClose }: UserDialogProps) {
  const queryClient = useQueryClient()
  const me = useUser()
  const isSelf = user?.id === me.id
  const isAdminAccount = user?.role === 'admin'

  const [username, setUsername] = useState(user?.username ?? '')
  const [firstName, setFirstName] = useState(user?.first_name ?? '')
  const [lastName, setLastName] = useState(user?.last_name ?? '')
  const [role, setRole] = useState<Role>(user?.role ?? 'student')
  const [group, setGroup] = useState(user?.group ? String(user.group) : NO_GROUP)
  const [password, setPassword] = useState('')
  const [isActive, setIsActive] = useState(user?.is_active ?? true)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        username: username.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      }
      if (!isAdminAccount) {
        body.role = role
        body.group = role === 'student' && group !== NO_GROUP ? Number(group) : null
      }
      if (password) body.password = password
      if (user && !isSelf) body.is_active = isActive
      return user
        ? api<AdminUser>(`/users/${user.id}/`, { method: 'PATCH', body })
        : api<AdminUser>('/users/', { method: 'POST', body })
    },
    onSuccess: () => {
      toast.success(user ? t("Foydalanuvchi ma'lumotlari saqlandi") : t('Foydalanuvchi yaratildi'))
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      void queryClient.invalidateQueries({ queryKey: ['groups'] })
      onClose()
    },
    onError: (error) => applyFormError(error, USER_FIELDS, setErrors),
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
          <DialogTitle>{user ? t('Foydalanuvchini tahrirlash') : t('Yangi foydalanuvchi')}</DialogTitle>
          <DialogDescription>
            {user
              ? t("Parolni o'zgartirmoqchi bo'lmasangiz, parol maydonini bo'sh qoldiring.")
              : t("Login va parolni foydalanuvchiga o'zingiz yetkazasiz.")}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="first_name" label={t('Ism')} error={errors.first_name}>
              <Input
                id="first_name"
                className="h-10"
                aria-invalid={Boolean(errors.first_name)}
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
              />
            </FormField>
            <FormField id="last_name" label={t('Familiya')} error={errors.last_name}>
              <Input
                id="last_name"
                className="h-10"
                aria-invalid={Boolean(errors.last_name)}
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
              />
            </FormField>
          </div>
          <FormField id="username" label={t('Login')} error={errors.username}>
            <Input
              id="username"
              className="h-10"
              autoCapitalize="none"
              autoComplete="off"
              aria-invalid={Boolean(errors.username)}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </FormField>
          {isAdminAccount ? null : (
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField id="role" label={t('Rol')} error={errors.role}>
                <Select value={role} onValueChange={(value) => setRole(value as Role)}>
                  <SelectTrigger id="role" className="h-10 w-full" aria-invalid={Boolean(errors.role)}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="student">{ROLE_LABELS.student}</SelectItem>
                    <SelectItem value="teacher">{ROLE_LABELS.teacher}</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              {role === 'student' ? (
                <FormField id="group" label={t('Guruh')} error={errors.group}>
                  <Select value={group} onValueChange={setGroup}>
                    <SelectTrigger id="group" className="h-10 w-full" aria-invalid={Boolean(errors.group)}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NO_GROUP}>{t('Biriktirilmagan')}</SelectItem>
                      {groups.map((item) => (
                        <SelectItem key={item.id} value={String(item.id)}>
                          {item.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
              ) : (
                <p className="self-end pb-2 text-xs text-muted-foreground">
                  {t("O'qituvchiga guruhlar «Guruhlar» sahifasida biriktiriladi.")}
                </p>
              )}
            </div>
          )}
          <FormField
            id="password"
            label={user ? t('Yangi parol') : t('Parol')}
            error={errors.password}
            hint={t("Kamida 8 belgi; faqat raqamlardan iborat bo'lmasin.")}
          >
            <PasswordInput
              id="password"
              className="h-10"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.password)}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </FormField>
          {user && !isSelf ? (
            <div className="grid gap-1">
              <label htmlFor="is_active" className="flex items-center gap-2 text-sm">
                <Checkbox
                  id="is_active"
                  checked={isActive}
                  onCheckedChange={(checked) => setIsActive(checked === true)}
                />
                {t('Faol (belgi olib tashlansa, foydalanuvchi tizimga kira olmaydi)')}
              </label>
              {errors.is_active ? <p className="text-xs text-destructive">{errors.is_active}</p> : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" size="lg" disabled={mutation.isPending} onClick={onClose}>
              {t('Bekor qilish')}
            </Button>
            <Button type="submit" size="lg" disabled={mutation.isPending || !username.trim() || (!user && !password)}>
              {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              {t('Saqlash')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

type RoleFilter = Role | 'all'

export function UsersPage() {
  const queryClient = useQueryClient()
  const me = useUser()
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
  const [editing, setEditing] = useState<AdminUser | 'new' | null>(null)
  const [deleting, setDeleting] = useState<AdminUser | null>(null)

  const users = useQuery({ queryKey: ['users'], queryFn: () => api<AdminUser[]>('/users/') })
  const groups = useQuery({ queryKey: ['groups'], queryFn: () => api<Group[]>('/groups/') })
  const groupList = useMemo(() => groups.data ?? [], [groups.data])

  const remove = useMutation({
    mutationFn: (user: AdminUser) => api(`/users/${user.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success(t("Foydalanuvchi o'chirildi"))
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      void queryClient.invalidateQueries({ queryKey: ['groups'] })
      setDeleting(null)
    },
    onError: (error) => {
      toast.error(errorMessage(error))
      setDeleting(null)
    },
  })

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (users.data ?? []).filter((user) => {
      if (roleFilter !== 'all' && user.role !== roleFilter) return false
      if (!needle) return true
      return `${user.first_name} ${user.last_name} ${user.username}`.toLowerCase().includes(needle)
    })
  }, [users.data, search, roleFilter])

  let content
  if (users.isPending) {
    content = <ListSkeleton />
  } else if (users.isError) {
    content = <ErrorState error={users.error} onRetry={() => void users.refetch()} />
  } else if (!filtered.length) {
    content = <EmptyState icon={Users} title={t('Foydalanuvchi topilmadi')} description={t("Qidiruv shartini o'zgartirib ko'ring.")} />
  } else {
    content = (
      <Card className="py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('Ism familiya')}</TableHead>
              <TableHead>{t('Login')}</TableHead>
              <TableHead>{t('Rol')}</TableHead>
              <TableHead>{t('Guruh')}</TableHead>
              <TableHead>{t('Holat')}</TableHead>
              <TableHead className="text-right">{t('Amallar')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{fullName(user)}</TableCell>
                <TableCell>{user.username}</TableCell>
                <TableCell>{ROLE_LABELS[user.role]}</TableCell>
                <TableCell className="max-w-56 truncate">
                  {user.role === 'student' ? groupNames(user.group ? [user.group] : [], groupList) : null}
                  {user.role === 'teacher' ? groupNames(user.teaching_groups, groupList) : null}
                  {user.role === 'admin' ? '—' : null}
                </TableCell>
                <TableCell>
                  {user.is_active ? (
                    <Badge variant="secondary">{t('Faol')}</Badge>
                  ) : (
                    <Badge variant="destructive">{t('Bloklangan')}</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      aria-label={t('{user}: tahrirlash', { user: fullName(user) })}
                      onClick={() => setEditing(user)}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      aria-label={t("{user}: o'chirish", { user: fullName(user) })}
                      disabled={user.id === me.id}
                      onClick={() => setDeleting(user)}
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
        title={t('Foydalanuvchilar')}
        description={t("O'qituvchi va talabalar hisoblarini boshqarish.")}
        actions={
          <Button size="lg" onClick={() => setEditing('new')}>
            <Plus aria-hidden="true" />
            {t("Foydalanuvchi qo'shish")}
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap gap-3">
        <Input
          type="search"
          className="h-10 max-w-xs"
          placeholder={t("Ism yoki login bo'yicha qidirish")}
          aria-label={t('Qidirish')}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <Select value={roleFilter} onValueChange={(value) => setRoleFilter(value as RoleFilter)}>
          <SelectTrigger className="h-10 w-44" aria-label={t("Rol bo'yicha saralash")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('Barcha rollar')}</SelectItem>
            <SelectItem value="student">{ROLE_LABELS.student}</SelectItem>
            <SelectItem value="teacher">{ROLE_LABELS.teacher}</SelectItem>
            <SelectItem value="admin">{ROLE_LABELS.admin}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {content}

      {editing ? (
        <UserDialog
          key={editing === 'new' ? 'new' : editing.id}
          user={editing === 'new' ? undefined : editing}
          groups={groupList}
          onClose={() => setEditing(null)}
        />
      ) : null}
      <ConfirmDialog
        open={Boolean(deleting)}
        title={t("Foydalanuvchini o'chirish")}
        description={
          deleting
            ? t("{deleting} butunlay o'chiriladi. Talaba bo'lsa, uning barcha yechimlari va baholari ham o'chadi. Bu amalni qaytarib bo'lmaydi.", { deleting: fullName(deleting) })
            : ''
        }
        confirmLabel={t("O'chirish")}
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
        onClose={() => setDeleting(null)}
      />
    </>
  )
}
