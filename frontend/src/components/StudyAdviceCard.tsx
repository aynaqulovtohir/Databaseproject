import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Lightbulb, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { StudyAdviceState } from '@/lib/types'

/** Qiynalayotgan laboratoriya: qaysi joyini tushunmagani va qanday bajarish bo'yicha tavsiya.
 *  Kamida bir necha noto'g'ri urinishdan keyin ko'rinadi. AI yoqilgan guruhda AI, nazorat guruhida xato turlari bo'yicha. */
export function StudyAdviceCard({ labId, solved }: { labId: number; solved: boolean }) {
  const queryClient = useQueryClient()
  const state = useQuery({
    queryKey: ['study-advice', labId],
    queryFn: () => api<StudyAdviceState>(`/labs/${labId}/study-advice/`),
  })

  const request = useMutation({
    mutationFn: () => api<StudyAdviceState>(`/labs/${labId}/study-advice/`, { method: 'POST' }),
    onSuccess: (data) => queryClient.setQueryData(['study-advice', labId], data),
    onError: (error) => toast.error(errorMessage(error)),
  })

  const data = state.data
  // Hali qiynalmagan (yoki yechib, tavsiya so'ramagan) talabaga karta ko'rsatilmaydi
  if (!data || (!data.advice && (solved || data.wrong_attempts < data.min_wrong))) return null
  const { advice } = data

  const button = data.can_request ? (
    <Button size="lg" variant={advice ? 'outline' : 'default'} disabled={request.isPending} onClick={() => request.mutate()}>
      {request.isPending ? (
        <Loader2 className="animate-spin" aria-hidden="true" />
      ) : advice ? (
        <RefreshCw aria-hidden="true" />
      ) : (
        <Lightbulb aria-hidden="true" />
      )}
      {request.isPending ? 'Tahlil qilinmoqda…' : advice ? "Yangi urinishlar bo'yicha yangilash" : 'Qayerda qiynalayotganimni tahlil qil'}
    </Button>
  ) : null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Tavsiya: qanday bajarish kerak
          {advice ? (
            <Badge variant="outline">{advice.source === 'ai' ? 'AI tahlili' : "Xato turlari bo'yicha"}</Badge>
          ) : null}
        </CardTitle>
        <CardDescription>
          {advice
            ? `${advice.attempts} ta urinishingiz tahlili · ${formatDateTime(advice.created_at)}`
            : `${data.wrong_attempts} ta urinishda xato bo'ldi. ${data.ai ? 'AI' : 'Tizim'} urinishlaringizni tahlil qilib, qaysi joyini tushunmaganingizni va laboratoriyani qanday bajarishni ko'rsatadi. Tayyor javob berilmaydi.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {advice ? (
          <>
            <p className="text-sm font-medium">{advice.summary}</p>
            {advice.struggles.length ? (
              <div className="grid gap-2">
                <h3 className="text-sm font-semibold">Qiyinchiliklar</h3>
                <ul className="grid gap-2">
                  {advice.struggles.map((item, index) => (
                    <li key={index} className="rounded-lg border bg-muted/30 p-3 text-sm">
                      <div className="font-medium">{item.title}</div>
                      <p className="mt-0.5 text-muted-foreground">{item.explanation}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="grid gap-2">
              <h3 className="text-sm font-semibold">Qadamlar</h3>
              <ol className="list-decimal space-y-1 pl-5 text-sm">
                {advice.steps.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
            </div>
            {advice.review.length ? (
              <div className="flex flex-wrap items-start gap-2 text-sm">
                <BookOpen className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span>
                  <span className="text-muted-foreground">Qayta o'qing: </span>
                  {advice.review.join('; ')}
                </span>
              </div>
            ) : null}
          </>
        ) : null}
        {button ? <div>{button}</div> : null}
      </CardContent>
    </Card>
  )
}
