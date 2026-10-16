import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ExternalLink, Loader2, Send } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { FormField } from '@/components/FormField'
import { PasswordInput } from '@/components/PasswordInput'
import { PageHeader } from '@/components/PageHeader'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { api, errorMessage, fieldErrors } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { formatDateTime } from '@/lib/format'
import { ROLE_LABELS, type TelegramLink, type TelegramStatus } from '@/lib/types'

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}

function AccountCard() {
  const user = useUser()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Hisob ma'lumotlari</CardTitle>
        <CardDescription>Ma'lumotlarni o'zgartirish uchun administratorga murojaat qiling.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="divide-y">
          <InfoRow label="Ism familiya" value={fullName(user)} />
          <InfoRow label="Login" value={user.username} />
          <InfoRow label="Rol" value={ROLE_LABELS[user.role]} />
          {user.role === 'student' ? <InfoRow label="Guruh" value={user.group?.name ?? 'Biriktirilmagan'} /> : null}
          {user.role === 'teacher' ? (
            <InfoRow
              label="Guruhlar"
              value={user.teaching_groups.map((group) => group.name).join(', ') || 'Biriktirilmagan'}
            />
          ) : null}
        </dl>
      </CardContent>
    </Card>
  )
}

function PasswordCard() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [repeatPassword, setRepeatPassword] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  const mutation = useMutation({
    mutationFn: () =>
      api('/auth/change-password/', {
        method: 'POST',
        body: { old_password: oldPassword, new_password: newPassword },
      }),
    onSuccess: () => {
      toast.success("Parol o'zgartirildi")
      setOldPassword('')
      setNewPassword('')
      setRepeatPassword('')
      setErrors({})
    },
    onError: (error) => {
      const fields = fieldErrors(error)
      setErrors(fields)
      if (!Object.keys(fields).length) toast.error(errorMessage(error))
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (newPassword !== repeatPassword) {
      setErrors({ repeat_password: 'Parollar bir xil emas.' })
      return
    }
    setErrors({})
    mutation.mutate()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Parolni o'zgartirish</CardTitle>
        <CardDescription>Kamida 8 belgi; faqat raqamlardan iborat bo'lmasin.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
          <FormField id="old_password" label="Joriy parol" error={errors.old_password}>
            <PasswordInput
              id="old_password"
              autoComplete="current-password"
              className="h-10"
              aria-invalid={Boolean(errors.old_password)}
              value={oldPassword}
              onChange={(event) => setOldPassword(event.target.value)}
            />
          </FormField>
          <FormField id="new_password" label="Yangi parol" error={errors.new_password}>
            <PasswordInput
              id="new_password"
              autoComplete="new-password"
              className="h-10"
              aria-invalid={Boolean(errors.new_password)}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </FormField>
          <FormField id="repeat_password" label="Yangi parolni takrorlang" error={errors.repeat_password}>
            <PasswordInput
              id="repeat_password"
              autoComplete="new-password"
              className="h-10"
              aria-invalid={Boolean(errors.repeat_password)}
              value={repeatPassword}
              onChange={(event) => setRepeatPassword(event.target.value)}
            />
          </FormField>
          <Button
            type="submit"
            size="lg"
            className="justify-self-start"
            disabled={mutation.isPending || !oldPassword || !newPassword || !repeatPassword}
          >
            {mutation.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
            Saqlash
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function TelegramCard() {
  const queryClient = useQueryClient()
  const [link, setLink] = useState<TelegramLink | null>(null)

  const status = useQuery({
    queryKey: ['telegram'],
    queryFn: () => api<TelegramStatus>('/telegram/'),
    // Havola berilgandan keyin bog'lanishni kutamiz: holat har 3 soniyada tekshiriladi
    refetchInterval: (query) => (link && !query.state.data?.linked ? 3000 : false),
  })

  const createLink = useMutation({
    mutationFn: () => api<TelegramLink>('/telegram/link/', { method: 'POST' }),
    onSuccess: setLink,
    onError: (error) => toast.error(errorMessage(error)),
  })

  const unlink = useMutation({
    mutationFn: () => api('/telegram/', { method: 'DELETE' }),
    onSuccess: () => {
      setLink(null)
      toast.success("Telegram bog'lanishi uzildi")
      void queryClient.invalidateQueries({ queryKey: ['telegram'] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  let content
  if (status.isPending) {
    content = <Skeleton className="h-10 w-full" />
  } else if (status.isError) {
    content = (
      <Alert variant="destructive">
        <AlertDescription>{errorMessage(status.error)}</AlertDescription>
      </Alert>
    )
  } else if (!status.data.configured) {
    content = (
      <p className="text-sm text-muted-foreground">
        Telegram bot hali sozlanmagan. Sozlangach, shu yerdan ulashingiz mumkin bo'ladi.
      </p>
    )
  } else if (status.data.linked) {
    content = (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="size-4 text-emerald-600" aria-hidden="true" />
          <span>
            Ulangan <span className="text-muted-foreground">({formatDateTime(status.data.linked_at)})</span>
          </span>
        </div>
        <Button variant="outline" size="lg" disabled={unlink.isPending} onClick={() => unlink.mutate()}>
          Uzish
        </Button>
      </div>
    )
  } else if (link) {
    content = (
      <div className="grid gap-3">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
          <li>Quyidagi tugma orqali botni oching.</li>
          <li>Botda «Start» tugmasini bosing.</li>
          <li>Bu sahifa o'zi yangilanadi.</li>
        </ol>
        <div className="flex flex-wrap items-center gap-3">
          <Button asChild size="lg">
            <a href={link.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink aria-hidden="true" />
              Botni ochish
            </a>
          </Button>
          <span className="text-xs text-muted-foreground">Havola {formatDateTime(link.expires_at)} gacha amal qiladi</span>
        </div>
      </div>
    )
  } else {
    content = (
      <Button size="lg" disabled={createLink.isPending} onClick={() => createLink.mutate()}>
        {createLink.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Send aria-hidden="true" />}
        Telegramni ulash
      </Button>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Telegram bildirishnomalari</CardTitle>
        <CardDescription>
          Yangi topshiriq, baho va muddat haqida botdan xabar olasiz. Xabarlarda ball va ismingiz yozilmaydi.
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}

export function ProfilePage() {
  return (
    <>
      <PageHeader title="Profil" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="grid content-start gap-4">
          <AccountCard />
          <TelegramCard />
        </div>
        <PasswordCard />
      </div>
    </>
  )
}
