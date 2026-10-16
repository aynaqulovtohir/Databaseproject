import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bug, Loader2, Shuffle, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { SqlCode } from '@/components/SqlCode'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { api, errorMessage } from '@/lib/api'
import type { BuggyCode, Lab } from '@/lib/types'

/** O'qituvchi: AI bilan yangi variant va "AI yozgan xatoli kod — xatoni toping" boshlang'ich kodi. */
export function LabGenerateCard({ lab }: { lab: Lab }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [domain, setDomain] = useState('')

  const variant = useMutation({
    mutationFn: () => api<Lab>(`/labs/${lab.id}/generate-variant/`, { method: 'POST', body: { domain } }),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['labs'] })
      toast.success("Variant yaratildi va qum qutida tekshirildi. Ko'rib chiqib, guruhlarga bering.")
      navigate(`/labs/${created.id}`)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  const buggy = useMutation({
    mutationFn: () => api<BuggyCode>(`/labs/${lab.id}/generate-buggy/`, { method: 'POST' }),
    onError: (error) => toast.error(errorMessage(error)),
  })
  const saveStarter = useMutation({
    mutationFn: (starter: string) => api<Lab>(`/labs/${lab.id}/`, { method: 'PATCH', body: { starter_sql: starter } }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['lab', lab.id], updated)
      toast.success(updated.starter_sql ? "Boshlang'ich kod saqlandi" : "Boshlang'ich kod olib tashlandi")
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI yordamida yaratish</CardTitle>
        <CardDescription>
          AI yozgan hamma narsa qum qutida haqiqatan ishga tushirib tekshiriladi. Natijani baribir o'zingiz ko'rib
          chiqing.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        <div className="grid gap-2">
          <div className="text-sm font-medium">Yangi variant</div>
          <p className="text-xs text-muted-foreground">
            Shu ko'nikmani boshqa sohada tekshiradigan laboratoriya: talabalar eski yechimni ko'chira olmaydi. Guruhlarsiz
            qoralama sifatida saqlanadi.
          </p>
          <div className="flex flex-wrap gap-2">
            <Input
              aria-label="Soha"
              className="max-w-64"
              placeholder="Soha (ixtiyoriy): kasalxona"
              maxLength={100}
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
            />
            <Button type="button" variant="outline" disabled={variant.isPending} onClick={() => variant.mutate()}>
              {variant.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Shuffle aria-hidden="true" />}
              {variant.isPending ? 'Yozilmoqda va tekshirilmoqda…' : 'Variant yaratish'}
            </Button>
          </div>
        </div>

        <div className="grid gap-2 border-t pt-4">
          <div className="text-sm font-medium">«Xatoni toping»: AI yozgan kodni tekshirish</div>
          <p className="text-xs text-muted-foreground">
            Ishonarli ko'rinadigan, xatosiz bajariladigan, lekin noto'g'ri natija beradigan kod. Talaba uni muharrirda
            boshlang'ich kod sifatida oladi va tuzatadi. Shartga «Bu kodni AI yozgan, xatolarini toping» deb qo'shib
            qo'ying.
          </p>
          {lab.starter_sql?.trim() ? (
            <div className="grid gap-2 rounded-lg border p-3">
              <div className="text-xs font-medium">Hozirgi boshlang'ich kod (talabaga ko'rinadi)</div>
              <SqlCode code={lab.starter_sql.trim()} />
              <Button
                type="button"
                variant="outline"
                className="justify-self-start"
                disabled={saveStarter.isPending}
                onClick={() => saveStarter.mutate('')}
              >
                <Trash2 aria-hidden="true" />
                Olib tashlash
              </Button>
            </div>
          ) : null}
          <Button
            type="button"
            variant="outline"
            className="justify-self-start"
            disabled={buggy.isPending}
            onClick={() => buggy.mutate()}
          >
            {buggy.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Bug aria-hidden="true" />}
            {buggy.isPending ? 'Yozilmoqda va tekshirilmoqda…' : 'Xatoli kod yaratish'}
          </Button>
          {buggy.data ? (
            <div className="grid gap-2 rounded-lg border p-3" aria-live="polite">
              <SqlCode code={buggy.data.buggy_sql} />
              <div className="text-xs font-medium">Xatolar (faqat sizga):</div>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {buggy.data.bugs.map((bug, index) => (
                  <li key={index}>{bug}</li>
                ))}
              </ul>
              <div className="text-xs font-medium">Tekshiruv natijasi (talaba ham shuni ko'radi):</div>
              <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                {buggy.data.differences.map((difference, index) => (
                  <li key={index}>{difference}</li>
                ))}
              </ul>
              <Button
                type="button"
                className="justify-self-start"
                disabled={saveStarter.isPending}
                onClick={() => saveStarter.mutate(buggy.data.buggy_sql)}
              >
                Boshlang'ich kod sifatida saqlash
              </Button>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
