import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleSlash, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { api, errorMessage } from '@/lib/api'
import { useAuth, useUser } from '@/lib/auth'
import { formatDateTime } from '@/lib/format'
import type { ConsentStatus } from '@/lib/types'

function useConsent(enabled = true) {
  return useQuery({ queryKey: ['consent'], queryFn: () => api<ConsentStatus>('/auth/consent/'), enabled })
}

function useDecide(onDone?: () => void) {
  const queryClient = useQueryClient()
  const { refreshUser } = useAuth()
  return useMutation({
    mutationFn: (agreed: boolean) => api<ConsentStatus>('/auth/consent/', { method: 'POST', body: { agreed } }),
    onSuccess: async (status) => {
      queryClient.setQueryData(['consent'], status)
      toast.success(status.agreed ? 'Rahmat! Roziligingiz saqlandi' : 'Qaroringiz saqlandi')
      await refreshUser()
      onDone?.()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
}

function ConsentText({ status }: { status: ConsentStatus }) {
  return (
    <div className="grid gap-3 text-sm leading-relaxed">
      {status.text.map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
      {status.contact ? <p className="text-muted-foreground">Savollar uchun: {status.contact}</p> : null}
    </div>
  )
}

/** Kirgandan keyin talabadan bir marta so'raladi. «Keyinroq» — shu sessiyada yana ko'rsatilmaydi. */
export function ConsentPrompt() {
  const user = useUser()
  const [postponed, setPostponed] = useState(false)
  const open = user.role === 'student' && user.consent_needed && !postponed
  const status = useConsent(open)
  const decide = useDecide()

  return (
    <Dialog open={open} onOpenChange={(next) => (!next && !decide.isPending ? setPostponed(true) : undefined)}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-lg" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{status.data?.title ?? 'Ilmiy tadqiqotda ishtirok etishga rozilik'}</DialogTitle>
          <DialogDescription>Iltimos, o'qib chiqing va qaroringizni belgilang.</DialogDescription>
        </DialogHeader>
        {status.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : status.isError ? (
          <ErrorState error={status.error} onRetry={() => void status.refetch()} />
        ) : (
          <ConsentText status={status.data} />
        )}
        <DialogFooter className="gap-2 sm:justify-between">
          <Button variant="ghost" size="lg" disabled={decide.isPending} onClick={() => setPostponed(true)}>
            Keyinroq
          </Button>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" size="lg" disabled={decide.isPending || !status.data} onClick={() => decide.mutate(false)}>
              Rozi emasman
            </Button>
            <Button size="lg" disabled={decide.isPending || !status.data} onClick={() => decide.mutate(true)}>
              {decide.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              Roziman
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Profil sahifasida: joriy qaror va uni o'zgartirish. */
export function ConsentCard() {
  const status = useConsent()
  const decide = useDecide()
  // Rozilik talab qilinmasa (RESEARCH_CONSENT_REQUIRED=False) karta ko'rsatilmaydi
  if (status.data && !status.data.required) return null

  let content
  if (status.isPending) content = <Skeleton className="h-24 w-full" />
  else if (status.isError) content = <ErrorState error={status.error} onRetry={() => void status.refetch()} />
  else {
    const { agreed, decided_at: decidedAt } = status.data
    content = (
      <div className="grid gap-4">
        <ConsentText status={status.data} />
        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
          <div className="flex items-center gap-2 text-sm">
            {agreed === true ? (
              <CheckCircle2 className="size-4 text-emerald-600" aria-hidden="true" />
            ) : (
              <CircleSlash className="size-4 text-muted-foreground" aria-hidden="true" />
            )}
            <span>
              {agreed === null ? 'Hali qaror bermagansiz' : agreed ? 'Rozisiz' : 'Rozi emassiz'}
              {decidedAt ? <span className="text-muted-foreground"> ({formatDateTime(decidedAt)})</span> : null}
            </span>
          </div>
          {agreed === true ? (
            <Button variant="outline" size="lg" disabled={decide.isPending} onClick={() => decide.mutate(false)}>
              Roziligimni qaytarib olaman
            </Button>
          ) : (
            <Button size="lg" disabled={decide.isPending} onClick={() => decide.mutate(true)}>
              {decide.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              Roziman
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ilmiy tadqiqot</CardTitle>
        <CardDescription>Ishtirok ixtiyoriy va bahoyingizga ta'sir qilmaydi.</CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
