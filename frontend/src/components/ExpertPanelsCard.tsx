import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, Copy, Link2, Loader2, Plus, RefreshCw, UserPlus } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { FormField } from '@/components/FormField'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { api, errorMessage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { ExpertInvite, ExpertPanel, ExpertResults, Quiz } from '@/lib/types'

function num(value: number | null, digits = 2) {
  return value === null ? '—' : value.toFixed(digits)
}

const VERDICT_VARIANT = { keep: 'secondary', revise: 'outline', remove: 'destructive' } as const

function expertLink(token: string) {
  return `${window.location.origin}/expert/${token}`
}

/** Yangi havola faqat bir marta ko'rsatiladi: bazada faqat uning xeshi saqlanadi */
function LinkDialog({ link, label, onClose }: { link: string; label: string; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>«{label}» uchun havola</DialogTitle>
          <DialogDescription>
            Havolani hozir nusxalang va ekspertga yuboring: xavfsizlik uchun u boshqa ko'rsatilmaydi (yo'qolsa, «Yangi havola»
            bilan qayta yaratasiz). Havolada test javoblari bor — faqat shu ekspertga bering.
          </DialogDescription>
        </DialogHeader>
        <Input readOnly className="h-10 font-mono text-xs" value={link} onFocus={(event) => event.target.select()} aria-label="Ekspert havolasi" />
        <DialogFooter>
          <Button
            size="lg"
            onClick={() => {
              void navigator.clipboard.writeText(link).then(
                () => toast.success('Havola nusxalandi'),
                () => toast.error("Nusxalab bo'lmadi: havolani qo'lda belgilab oling"),
              )
            }}
          >
            <Copy aria-hidden="true" />
            Nusxalash
          </Button>
          <Button variant="outline" size="lg" onClick={onClose}>
            Yopish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function CreatePanelDialog({ quiz, onClose, onCreated }: { quiz: Quiz; onClose: () => void; onCreated: (panel: ExpertPanel) => void }) {
  const [title, setTitle] = useState('1-bosqich')
  const [construct, setConstruct] = useState('')
  const [instructions, setInstructions] = useState('')
  const [closesAt, setClosesAt] = useState('')
  const create = useMutation({
    mutationFn: () =>
      api<ExpertPanel>('/expert-panels/', {
        method: 'POST',
        body: { quiz: quiz.id, title: title.trim(), construct: construct.trim(), instructions, closes_at: closesAt ? new Date(closesAt).toISOString() : null },
      }),
    onSuccess: onCreated,
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <Dialog open onOpenChange={(open) => (open || create.isPending ? undefined : onClose())}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Ekspert baholashini boshlash</DialogTitle>
          <DialogDescription>
            Testning hozirgi savollari nusxalanadi: ekspertlar shu versiyani baholaydi. Savollarni tuzatgach, yangi bosqich oching.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <FormField id="panel_title" label="Nomi">
            <Input id="panel_title" className="h-10" maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} />
          </FormField>
          <FormField id="panel_construct" label="Test nimani o'lchaydi" hint="Ekspert savollarning shu tushunchaga mosligini baholaydi">
            <Textarea
              id="panel_construct"
              rows={2}
              maxLength={2000}
              placeholder="Masalan: talabaning ma'lumotlar bazasini loyihalash bo'yicha bilimi (ER-model, kalitlar, normallashtirish)"
              value={construct}
              onChange={(event) => setConstruct(event.target.value)}
            />
          </FormField>
          <FormField id="panel_instructions" label="Ekspertga qo'shimcha ko'rsatma (ixtiyoriy)">
            <Textarea id="panel_instructions" rows={3} maxLength={3000} value={instructions} onChange={(event) => setInstructions(event.target.value)} />
          </FormField>
          <FormField id="panel_closes" label="Tugash vaqti (ixtiyoriy)">
            <Input id="panel_closes" type="datetime-local" className="h-10 w-auto" value={closesAt} onChange={(event) => setClosesAt(event.target.value)} />
          </FormField>
        </div>
        <DialogFooter>
          <Button variant="outline" size="lg" disabled={create.isPending} onClick={onClose}>
            Bekor qilish
          </Button>
          <Button size="lg" disabled={create.isPending || !title.trim() || !construct.trim()} onClick={() => create.mutate()}>
            {create.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
            Boshlash
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function InviteStatus({ invite }: { invite: ExpertInvite }) {
  if (invite.revoked) return <Badge variant="outline">Bekor qilingan</Badge>
  if (invite.submitted_at) return <Badge>Yuborgan · {formatDateTime(invite.submitted_at)}</Badge>
  if (invite.started) return <Badge variant="secondary">Baholamoqda ({invite.rated} ta savol)</Badge>
  return <Badge variant="outline">Ochmagan</Badge>
}

function ResultsView({ results }: { results: ExpertResults }) {
  const { summary } = results
  if (results.experts < results.min_experts) {
    return (
      <p className="text-sm text-muted-foreground">
        Natija kamida {results.min_experts} ta ekspert baholarini yuborgach hisoblanadi (tavsiya: {results.recommended_experts}–10 ta).
        Hozir: {results.experts} ta.
      </p>
    )
  }
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border bg-card p-3">
          <div className="text-sm text-muted-foreground">S-CVI/Ave</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular-nums">{num(summary.s_cvi_ave)}</span>
            <Badge variant={summary.s_cvi_ave_ok ? 'secondary' : 'outline'}>{summary.s_cvi_ave_ok ? 'yetarli' : `talab ≥ ${summary.s_cvi_ave_target}`}</Badge>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-3">
          <div className="text-sm text-muted-foreground">S-CVI/UA</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular-nums">{num(summary.s_cvi_ua)}</span>
            <Badge variant={summary.s_cvi_ua_ok ? 'secondary' : 'outline'}>{summary.s_cvi_ua_ok ? 'yetarli' : `talab ≥ ${summary.s_cvi_ua_target}`}</Badge>
          </div>
        </div>
        <div className="rounded-xl border bg-card p-3">
          <div className="text-sm text-muted-foreground">Savollar</div>
          <div className="mt-1 text-sm tabular-nums">
            {summary.keep} qoldirish · {summary.revise} qayta ko'rish · {summary.remove} olib tashlash
          </div>
          <div className="mt-1 text-xs text-muted-foreground">CVI (CVR o'rtachasi): {num(summary.cvi)}</div>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {results.experts} ta ekspert.{' '}
        {results.cvr_testable
          ? `CVR kritik qiymati ${num(results.cvr_critical)} (α = 0.05, Ayre & Scally, 2014).`
          : "5 tadan kam ekspert: CVR ning statistik ahamiyatini tekshirib bo'lmaydi, hamma ekspert «zarur» deyishi talab qilinadi."}{' '}
        I-CVI talabi: ≥ {num(results.i_cvi_target)} (Lynn, 1986).
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Savol</TableHead>
            <TableHead className="text-right" title="«Zarur» deganlar soni va Lawshe CVR">
              CVR
            </TableHead>
            <TableHead className="text-right" title="Mosligini 3-4 deganlar ulushi">
              I-CVI
            </TableHead>
            <TableHead className="text-right" title="Modifikatsiyalangan kappa: tasodifiy kelishuv hisobga olingan">
              k*
            </TableHead>
            <TableHead className="text-right">Aniqlik</TableHead>
            <TableHead>Xulosa</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.items.map((item) => (
            <TableRow key={item.key} className="align-top">
              <TableCell className="max-w-md whitespace-normal">
                <div className="text-sm">
                  {item.order}. {item.text}
                </div>
                {item.comments.length ? (
                  <ul className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
                    {item.comments.map((comment, index) => (
                      <li key={index}>«{comment}»</li>
                    ))}
                  </ul>
                ) : null}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {num(item.cvr)}
                <span className="block text-xs text-muted-foreground">
                  {item.essential} / {results.experts} zarur
                </span>
              </TableCell>
              <TableCell className="text-right tabular-nums">{num(item.i_cvi)}</TableCell>
              <TableCell className="text-right tabular-nums">
                {num(item.kappa)}
                {item.kappa_label ? <span className="block text-xs text-muted-foreground">{item.kappa_label}</span> : null}
              </TableCell>
              <TableCell className="text-right tabular-nums">{num(item.clarity, 1)}</TableCell>
              <TableCell>{item.verdict ? <Badge variant={VERDICT_VARIANT[item.verdict.key]}>{item.verdict.label}</Badge> : null}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <details className="rounded-xl border bg-card p-3">
        <summary className="cursor-pointer text-sm font-medium">Ekspertlar ro'yxati (dissertatsiya ilovasi uchun)</summary>
        <ol className="mt-2 grid list-decimal gap-1 pl-5 text-sm">
          {results.panel_experts.map((expert, index) => (
            <li key={index}>
              {expert.full_name}
              {[expert.degree, expert.position, expert.workplace].filter(Boolean).length
                ? ` — ${[expert.degree, expert.position, expert.workplace].filter(Boolean).join(', ')}`
                : ''}
              {expert.experience_years !== null && expert.experience_years !== undefined ? `, staj ${expert.experience_years} yil` : ''}
            </li>
          ))}
        </ol>
      </details>
    </div>
  )
}

function PanelView({ panelId }: { panelId: number }) {
  const queryClient = useQueryClient()
  const [label, setLabel] = useState('')
  const [shown, setShown] = useState<{ link: string; label: string } | null>(null)
  const panel = useQuery({ queryKey: ['expert-panel', panelId], queryFn: () => api<ExpertPanel>(`/expert-panels/${panelId}/`) })

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['expert-panel', panelId] })
    void queryClient.invalidateQueries({ queryKey: ['expert-panels'] })
  }

  const invite = useMutation({
    mutationFn: () => api<{ invite: ExpertInvite; token: string }>(`/expert-panels/${panelId}/invites/`, { method: 'POST', body: { label: label.trim() } }),
    onSuccess: (data) => {
      setShown({ link: expertLink(data.token), label: data.invite.label })
      setLabel('')
      refresh()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  const operate = useMutation({
    mutationFn: ({ id, operation }: { id: number; operation: 'renew' | 'revoke' }) =>
      api<{ invite: ExpertInvite; token?: string }>(`/expert-panels/${panelId}/invites/${id}/${operation}/`, { method: 'POST' }),
    onSuccess: (data) => {
      if (data.token) setShown({ link: expertLink(data.token), label: data.invite.label })
      else toast.success('Havola bekor qilindi')
      refresh()
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  if (panel.isPending) return <ListSkeleton rows={2} />
  if (panel.isError) return <ErrorState error={panel.error} onRetry={() => void panel.refetch()} />
  const data = panel.data

  return (
    <div className="grid gap-4">
      <div className="text-sm text-muted-foreground">
        {data.items_count} ta savol · {formatDateTime(data.created_at)} dagi versiya
        {data.closes_at ? ` · ${formatDateTime(data.closes_at)} gacha` : ''}
      </div>
      <div className="grid gap-2">
        <h3 className="text-sm font-semibold">Ekspertlar</h3>
        {data.invites.length ? (
          <ul className="grid gap-1.5">
            {data.invites.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm">
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
                <InviteStatus invite={item} />
                {item.submitted_at ? null : (
                  <Button variant="ghost" size="sm" disabled={operate.isPending} onClick={() => operate.mutate({ id: item.id, operation: 'renew' })}>
                    <RefreshCw aria-hidden="true" />
                    Yangi havola
                  </Button>
                )}
                {item.revoked ? null : (
                  <Button variant="ghost" size="sm" disabled={operate.isPending} onClick={() => operate.mutate({ id: item.id, operation: 'revoke' })}>
                    <Ban aria-hidden="true" />
                    Bekor qilish
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Hali ekspert qo'shilmagan.</p>
        )}
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (label.trim()) invite.mutate()
          }}
        >
          <Input
            aria-label="Ekspert belgisi"
            className="h-10 min-w-0 flex-1"
            maxLength={200}
            placeholder="Masalan: 1-ekspert, TATU, dotsent"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
          <Button type="submit" variant="outline" size="lg" disabled={invite.isPending || !label.trim()}>
            <UserPlus aria-hidden="true" />
            Havola yaratish
          </Button>
        </form>
      </div>
      {data.results ? <ResultsView results={data.results} /> : null}
      {shown ? <LinkDialog link={shown.link} label={shown.label} onClose={() => setShown(null)} /> : null}
    </div>
  )
}

/** Test sahifasida: ekspert baholashi (mazmun validligi — Lawshe CVR, CVI) */
export function ExpertPanelsCard({ quiz }: { quiz: Quiz }) {
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const panels = useQuery({
    queryKey: ['expert-panels', quiz.id],
    queryFn: () => api<ExpertPanel[]>(`/expert-panels/?quiz=${quiz.id}`),
  })

  const list = panels.data ?? []
  const current = selected ?? list[0]?.id ?? null

  let content
  if (panels.isPending) content = <ListSkeleton rows={2} />
  else if (panels.isError) content = <ErrorState error={panels.error} onRetry={() => void panels.refetch()} />
  else if (!list.length)
    content = (
      <EmptyState
        icon={Link2}
        title="Hali ekspert baholashi yo'q"
        description="Tajribadan oldin test savollarini 5–10 ta ekspertga baholating: bu testning mazmun validligini isbotlaydi."
        action={
          <Button size="lg" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" />
            Baholashni boshlash
          </Button>
        }
      />
    )
  else
    content = (
      <div className="grid gap-4">
        <div className="flex flex-wrap items-center gap-2">
          {list.map((panel) => (
            <Button key={panel.id} size="sm" variant={panel.id === current ? 'default' : 'outline'} onClick={() => setSelected(panel.id)}>
              {panel.title}
            </Button>
          ))}
          <Button size="sm" variant="ghost" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" />
            Yangi bosqich
          </Button>
        </div>
        {current ? <PanelView key={current} panelId={current} /> : null}
      </div>
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ekspert baholashi (mazmun validligi)</CardTitle>
        <CardDescription>
          Ekspertlar har bir savolni zarurligi (Lawshe CVR), mosligi (CVI) va aniqligi bo'yicha baholaydi. Ekspertga akkaunt kerak
          emas: har biriga shaxsiy havola yuborasiz. Natija tadqiqot eksportida ham bor (ekspert_baholash.csv, ekspertlar ismisiz).
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
      {creating ? (
        <CreatePanelDialog
          quiz={quiz}
          onClose={() => setCreating(false)}
          onCreated={(panel) => {
            setCreating(false)
            setSelected(panel.id)
            void queryClient.invalidateQueries({ queryKey: ['expert-panels', quiz.id] })
          }}
        />
      ) : null}
    </Card>
  )
}
