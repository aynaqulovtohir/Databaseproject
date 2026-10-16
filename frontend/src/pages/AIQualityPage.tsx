import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BotMessageSquare, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { PageHeader } from '@/components/PageHeader'
import { SqlCode } from '@/components/SqlCode'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import type { AIQualityItem, AIQualityState, AIRating } from '@/lib/types'

function ItemCard({ item, state }: { item: AIQualityItem; state: AIQualityState }) {
  const queryClient = useQueryClient()
  const [comment, setComment] = useState('')
  const rate = useMutation({
    mutationFn: (rating: AIRating) =>
      api<AIQualityState>('/ai-quality/', {
        method: 'POST',
        body: { attempt: item.attempt, kind: item.kind, level: item.level, rating, comment },
      }),
    onSuccess: (next) => {
      queryClient.setQueryData(['ai-quality'], next)
      setComment('')
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          {item.kind_label}
          {item.kind === 'hint' ? <Badge variant="outline">{item.level}-daraja</Badge> : null}
        </CardTitle>
        <CardDescription>
          {item.lab.title} · talaba ishi {item.is_correct ? "to'g'ri" : "noto'g'ri"} edi. Talaba ismi ko'rsatilmaydi.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <details className="rounded-lg border p-3">
          <summary className="cursor-pointer text-sm font-medium select-none">Laboratoriya sharti</summary>
          <p className="mt-2 text-sm whitespace-pre-wrap">{item.lab.description}</p>
        </details>
        <div className="grid min-w-0 gap-1.5">
          <h3 className="text-sm font-medium">Talaba ishi</h3>
          <SqlCode code={item.work || '—'} />
          {item.differences.length ? (
            <ul className="grid list-disc gap-0.5 pl-5 text-xs text-muted-foreground">
              {item.differences.slice(0, 6).map((difference) => (
                <li key={difference}>{difference}</li>
              ))}
            </ul>
          ) : null}
        </div>
        {item.explanation ? (
          <div className="grid gap-1.5">
            <h3 className="text-sm font-medium">Talabaning tushuntirishi (AI bahosi: {item.verdict})</h3>
            <p className="rounded-lg border p-3 text-sm whitespace-pre-wrap">{item.explanation}</p>
          </div>
        ) : null}
        <div className="grid gap-1.5">
          <h3 className="text-sm font-medium">AI yozgan matn</h3>
          <p className="rounded-lg border bg-muted/40 p-3 text-sm whitespace-pre-wrap">{item.text}</p>
        </div>
        <Textarea
          aria-label="Izoh (ixtiyoriy)"
          placeholder="Izoh (ixtiyoriy): nimasi noto'g'ri yoki ortiqcha?"
          maxLength={1000}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          {state.ratings.map((rating) => (
            <Button
              key={rating.value}
              type="button"
              variant={rating.value === 'helpful' ? 'default' : 'outline'}
              disabled={rate.isPending}
              onClick={() => rate.mutate(rating.value)}
            >
              {rate.isPending && rate.variables === rating.value ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
              {rating.label}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function SummaryCard({ state }: { state: AIQualityState }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Xulosa</CardTitle>
        <CardDescription>
          Barcha o'qituvchilarning baholari (guruhlaringiz bo'yicha): ulush va 95% ishonch oralig'i (Wilson). Siz{' '}
          {state.rated_by_me} ta matnni baholadingiz.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Turi</TableHead>
              {state.ratings.map((rating) => (
                <TableHead key={rating.value}>{rating.label}</TableHead>
              ))}
              <TableHead>Jami</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.summary.map((row) => (
              <TableRow key={row.kind}>
                <TableCell className="font-medium">{row.label}</TableCell>
                {row.ratings.map((item) => (
                  <TableCell key={item.rating} className="tabular-nums">
                    {item.percent === null ? (
                      '—'
                    ) : (
                      <div className="grid">
                        <span>
                          {item.percent}% <span className="text-muted-foreground">({item.count})</span>
                        </span>
                        {item.ci95 ? (
                          <span className="text-xs text-muted-foreground">
                            95% oraliq: {item.ci95[0]}–{item.ci95[1]}%
                          </span>
                        ) : null}
                      </div>
                    )}
                  </TableCell>
                ))}
                <TableCell className="tabular-nums">{row.total}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

export function AIQualityPage() {
  const state = useQuery({ queryKey: ['ai-quality'], queryFn: () => api<AIQualityState>('/ai-quality/') })

  let content
  if (state.isPending) {
    content = <ListSkeleton />
  } else if (state.isError) {
    content = <ErrorState error={state.error} onRetry={() => void state.refetch()} />
  } else {
    content = (
      <div className="grid gap-4">
        {state.data.next ? (
          <ItemCard key={`${state.data.next.attempt}-${state.data.next.kind}-${state.data.next.level}`} item={state.data.next} state={state.data} />
        ) : (
          <EmptyState
            icon={BotMessageSquare}
            title="Baholanadigan AI matni qolmadi"
            description="Talabalar yangi AI maslahatlari olganda yoki yechimini tushuntirganda bu yerda yana paydo bo'ladi."
          />
        )}
        <SummaryCard state={state.data} />
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="AI sifati"
        description="AI yozgan maslahatlar va izohlarni baholang: foydali, tushunarsiz, noto'g'ri yoki javobni aytib qo'ygan. Natija AI qanchalik ishonchli ekanini ko'rsatadi (ilmiy eksportda — ai_sifati.csv). Murabbiy va buyurtmachi suhbatlari bu yerga kirmaydi: ular talabaga shaxsiy deb va'da qilingan."
      />
      {content}
    </>
  )
}
