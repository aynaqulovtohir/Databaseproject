import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { ErrorState } from '@/components/States'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { api, ApiError, errorMessage } from '@/lib/api'
import { MAX_SCORE, type Analysis, type AnalysisIssue } from '@/lib/types'

const SEVERITY_LABELS: Record<AnalysisIssue['severity'], string> = {
  high: 'Jiddiy',
  medium: "O'rtacha",
  low: 'Kichik',
}

const SEVERITY_CLASSES: Record<AnalysisIssue['severity'], string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-slate-100 text-slate-700',
}

// eslint-disable-next-line react/only-export-components
export function useAnalysis(submissionId: number, enabled = true) {
  return useQuery({
    queryKey: ['analysis', submissionId],
    queryFn: () => api<Analysis>(`/submissions/${submissionId}/analysis/`),
    enabled,
    // Tahlil fonda bajariladi: tugaguncha holat qayta-qayta so'raladi
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'processing' ? 4000 : false
    },
  })
}

interface AnalysisPanelProps {
  submissionId: number
  /** Admin yoki o'qituvchi: taklif qilingan ball va xato matni ham ko'rsatiladi */
  staff?: boolean
}

export function AnalysisPanel({ submissionId, staff = false }: AnalysisPanelProps) {
  const queryClient = useQueryClient()
  const query = useAnalysis(submissionId)

  const retry = useMutation({
    mutationFn: () => api<Analysis>(`/submissions/${submissionId}/analysis/retry/`, { method: 'POST' }),
    onSuccess: (analysis) => queryClient.setQueryData(['analysis', submissionId], analysis),
    onError: (error) => toast.error(errorMessage(error)),
  })

  if (query.isPending) return <Skeleton className="h-24 w-full" />
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) {
      return <p className="text-sm text-muted-foreground">Bu yechim uchun AI tahlili yo'q.</p>
    }
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  }

  const analysis = query.data

  if (analysis.status === 'pending' || analysis.status === 'processing') {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        {analysis.status === 'pending' ? 'Tahlil navbatda turibdi…' : 'AI yechimni tahlil qilmoqda…'}
      </div>
    )
  }

  if (analysis.status === 'failed') {
    return (
      <Alert variant="destructive">
        <AlertDescription className="grid gap-2">
          <span>
            {staff
              ? `AI tahlili xato bilan tugadi${analysis.error_message ? `: ${analysis.error_message}` : '.'}`
              : "AI tahlilini bajarib bo'lmadi. O'qituvchi yechimni o'zi tekshiradi."}
          </span>
          {staff ? (
            <Button
              variant="outline"
              size="sm"
              className="justify-self-start"
              disabled={retry.isPending}
              onClick={() => retry.mutate()}
            >
              <RefreshCw className={retry.isPending ? 'animate-spin' : undefined} aria-hidden="true" />
              Qayta tahlil qilish
            </Button>
          ) : null}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="grid gap-4 text-sm">
      {staff && analysis.suggested_score != null ? (
        <div className="rounded-lg border bg-muted/40 p-3">
          <div className="font-medium">
            AI taklif qilgan ball: {analysis.suggested_score} / {MAX_SCORE}
          </div>
          {analysis.score_rationale ? (
            <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{analysis.score_rationale}</p>
          ) : null}
          <p className="mt-2 text-xs text-muted-foreground">
            Bu faqat taklif: yakuniy bahoni siz qo'yasiz. Talaba bu ballni ko'rmaydi.
          </p>
        </div>
      ) : null}

      {analysis.summary ? <p className="whitespace-pre-wrap">{analysis.summary}</p> : null}

      <div>
        <h4 className="mb-2 font-medium">Topilgan muammolar</h4>
        {analysis.issues.length ? (
          <ul className="grid gap-2">
            {analysis.issues.map((issue, index) => (
              <li key={index} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className={SEVERITY_CLASSES[issue.severity]}>{SEVERITY_LABELS[issue.severity]}</Badge>
                  <span className="font-medium">{issue.title}</span>
                </div>
                <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{issue.explanation}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground">Muammo topilmadi.</p>
        )}
      </div>

      {analysis.recommendations.length ? (
        <div>
          <h4 className="mb-2 font-medium">Tavsiyalar</h4>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            {analysis.recommendations.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {staff && analysis.model_name ? (
        <p className="text-xs text-muted-foreground">Model: {analysis.model_name}</p>
      ) : null}
    </div>
  )
}
