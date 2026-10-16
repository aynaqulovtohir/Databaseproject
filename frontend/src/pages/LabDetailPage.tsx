import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  BookOpen,
  Copy,
  Lightbulb,
  Loader2,
  Pencil,
  ShieldCheck,
  Sparkles,
  Trash2,
  TriangleAlert,
  Users,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErEditor } from '@/components/ErEditor'
import { ErLabRunner } from '@/components/ErLabRunner'
import { InterviewPanel, RequirementList } from '@/components/InterviewPanel'
import { LabCoach, type LabWork } from '@/components/LabCoach'
import { PeerReviewPanel } from '@/components/PeerReviewPanel'
import { LabDialog } from '@/components/LabDialog'
import { LabGenerateCard } from '@/components/LabGenerateCard'
import { LabRunner } from '@/components/LabRunner'
import { NormLabRunner, NormTaskView } from '@/components/NormLabRunner'
import { PageHeader } from '@/components/PageHeader'
import { VerdictBadge } from '@/components/SelfExplain'
import { SqlCode } from '@/components/SqlCode'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, ApiError, errorMessage } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { formatDateTime } from '@/lib/format'
import { groupNames, useGroupOptions } from '@/lib/groups'
import { supportsGeneration } from '@/lib/labs'
import {
  GRADE_SOURCE_LABELS,
  MAX_SCORE,
  type ErDiagram,
  type Lab,
  type LabRunResult,
  type LabMistakesReport,
  type LabStudentProgress,
  type SimilarityReport,
  type SimilarPair,
  type SimilarWork,
} from '@/lib/types'
import { LabProgressBadge } from '@/pages/LabsPage'
import { cn } from '@/lib/utils'
import { NotFoundPage } from '@/pages/NotFoundPage'

function BackLink() {
  return (
    <Link
      to="/labs"
      className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden="true" />
      Virtual laboratoriya
    </Link>
  )
}

/** Nazariya matni: ``` bilan ajratilgan qismlar kod sifatida, qolgani oddiy matn (HTML ishlatilmaydi). */
function TheoryText({ text }: { text: string }) {
  const parts = text.split(/```[a-z]*\n?/)
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {parts.map((part, index) =>
        !part.trim() ? null : index % 2 === 1 ? (
          <SqlCode key={index} code={part.trimEnd()} />
        ) : (
          <p key={index} className="text-sm whitespace-pre-wrap">
            {part.trim()}
          </p>
        ),
      )}
    </div>
  )
}

/** ER → SQL: talabaga berilgan ER-model. Tor ustunda u o'qib bo'lmas darajada kichrayadi, shuning uchun
 * alohida, to'liq kenglikdagi kartada ko'rsatiladi. */
function GivenModelCard({ lab }: { lab: Lab }) {
  if (lab.kind !== 'sql' || !lab.given_diagram?.entities.length) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Berilgan ER-model</CardTitle>
        <CardDescription>
          Shu model bo'yicha jadvallarni yarating. Diagrammani surib va kattalashtirib ko'rish mumkin.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ErEditor value={lab.given_diagram} />
      </CardContent>
    </Card>
  )
}

function ConditionCard({ lab }: { lab: Lab }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Laboratoriya sharti</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-[minmax(0,1fr)] gap-4">
        <p className="text-sm whitespace-pre-wrap">{lab.description}</p>
        {lab.kind === 'norm' && lab.norm_task ? <NormTaskView task={lab.norm_task} /> : null}
        {lab.kind === 'sql' && lab.plan_query?.trim() ? (
          <div>
            <h3 className="mb-1 text-sm font-medium">Tekshiriladigan so'rov</h3>
            <p className="mb-2 text-xs text-muted-foreground">
              Kodingizdan keyin shu so'rovning rejasi (EXPLAIN) tekshiriladi. So'rovning o'zini yozish shart emas.
            </p>
            <SqlCode code={lab.plan_query.trim()} />
          </div>
        ) : null}
        {lab.theory.trim() ? (
          <details open className="group rounded-lg border bg-muted/30 p-3">
            <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium select-none">
              <BookOpen className="size-4 shrink-0" aria-hidden="true" />
              Nazariya va namuna
            </summary>
            <div className="mt-3">
              <TheoryText text={lab.theory} />
            </div>
          </details>
        ) : null}
        {lab.kind !== 'sql' ? null : lab.setup_sql.trim() ? (
          <div>
            <h3 className="mb-1 text-sm font-medium">Tayyor jadvallar</h3>
            <p className="mb-2 text-xs text-muted-foreground">
              Har bir ishga tushirishdan oldin baza shu holatga qaytariladi. Bu kodni qayta yozish shart emas.
            </p>
            <SqlCode code={lab.setup_sql.trim()} />
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Tayyor jadvallar yo'q: har bir ishga tushirish bo'sh bazadan boshlanadi.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// ---------- Admin va o'qituvchi ----------

/** Eng ko'p uchraydigan xatolar: o'qituvchi keyingi darsda nimani qayta tushuntirishni ko'radi. */
/** Hisobotning AI xulosasi: keyingi dars uchun tavsiyalar (AI'ga faqat anonim sonlar yuboriladi) */
function MistakesSummary({ labId, group }: { labId: number; group: string }) {
  const summary = useMutation({
    mutationFn: () =>
      api<{ summary: string }>(`/labs/${labId}/mistakes/summary/${group ? `?group=${group}` : ''}`, { method: 'POST' }),
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <div className="grid gap-2 border-t pt-3">
      <Button
        type="button"
        variant="outline"
        className="justify-self-start"
        disabled={summary.isPending}
        onClick={() => summary.mutate()}
      >
        {summary.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
        AI xulosasi: keyingi darsda nima qilish kerak
      </Button>
      {summary.data ? <p className="text-sm whitespace-pre-wrap">{summary.data.summary}</p> : null}
      <p className="text-xs text-muted-foreground">AI'ga faqat shu hisobotdagi sonlar yuboriladi, talabalar ismi emas.</p>
    </div>
  )
}

function MistakesCard({ lab }: { lab: Lab }) {
  const { groups } = useGroupOptions()
  const [group, setGroup] = useState('')
  const report = useQuery({
    queryKey: ['lab-mistakes', lab.id, group],
    queryFn: () => api<LabMistakesReport>(`/labs/${lab.id}/mistakes/${group ? `?group=${group}` : ''}`),
  })
  const labGroups = groups.filter((item) => lab.groups?.includes(item.id))

  let content
  if (report.isPending) {
    content = <ListSkeleton rows={2} />
  } else if (report.isError) {
    content = <ErrorState error={report.error} onRetry={() => void report.refetch()} />
  } else if (!report.data.items.length) {
    content = (
      <EmptyState
        icon={TriangleAlert}
        title={report.data.attempted ? "Noto'g'ri urinishlar yo'q" : 'Hali hech kim urinib ko\'rmagan'}
      />
    )
  } else {
    const data = report.data
    content = (
      <div className="grid gap-4">
        <p className="text-sm text-muted-foreground">
          {data.attempted} / {data.students} talaba urinib ko'rgan, {data.solved} tasi yechgan,{' '}
          <span className={data.stuck ? 'font-medium text-foreground' : ''}>{data.stuck} tasi hali qiynalmoqda</span>.
          Noto'g'ri urinishlar: {data.wrong_attempts}.
        </p>
        <ol className="grid gap-3">
          {data.items.map((item, index) => (
            <li key={index} className="grid gap-1.5">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="min-w-0 break-words">
                  <span className="mr-1.5 text-xs text-muted-foreground">
                    {item.kind === 'error' ? 'SQL xatosi' : 'Natija farqi'}
                  </span>
                  {item.text}
                </span>
                <span className="shrink-0 text-right tabular-nums">
                  <span className="font-medium">{item.share}%</span>
                  <span className="block text-xs text-muted-foreground">
                    {item.students} talaba · {item.attempts} urinish
                  </span>
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                <div className="h-full rounded-full bg-primary/70" style={{ width: `${item.share}%` }} />
              </div>
              {item.tip ? (
                <p className="flex gap-1.5 text-xs text-muted-foreground">
                  <Lightbulb className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  {item.tip}
                </p>
              ) : null}
            </li>
          ))}
        </ol>
        <MistakesSummary key={group} labId={lab.id} group={group} />
      </div>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Eng ko'p uchraydigan xatolar</CardTitle>
        <CardDescription>
          Foiz — urinib ko'rgan talabalarning qanchasi shu xatoga kamida bir marta duch kelgani. Keyingi darsda
          nimani qayta tushuntirish kerakligini ko'rsatadi.
        </CardDescription>
        {labGroups.length > 1 ? (
          <select
            aria-label="Guruh"
            className="mt-2 h-9 justify-self-start rounded-md border bg-background px-2 text-sm"
            value={group}
            onChange={(event) => setGroup(event.target.value)}
          >
            <option value="">Barcha guruhlar</option>
            {labGroups.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        ) : null}
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}

function ProgressCard({ lab }: { lab: Lab }) {
  const [viewing, setViewing] = useState<LabStudentProgress | null>(null)
  const progress = useQuery({
    queryKey: ['lab-progress', lab.id],
    queryFn: () => api<LabStudentProgress[]>(`/labs/${lab.id}/progress/`),
  })

  let content
  if (progress.isPending) {
    content = <ListSkeleton rows={2} />
  } else if (progress.isError) {
    content = <ErrorState error={progress.error} onRetry={() => void progress.refetch()} />
  } else if (!progress.data.length) {
    content = <EmptyState icon={Users} title="Bu guruhlarda hali talaba yo'q" />
  } else {
    content = (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Talaba</TableHead>
            <TableHead>Guruh</TableHead>
            <TableHead>Holat</TableHead>
            <TableHead className="text-right">Ball</TableHead>
            <TableHead>Oxirgi urinish</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {progress.data.map((student) => (
            <TableRow key={student.id}>
              <TableCell className="font-medium">{fullName(student)}</TableCell>
              <TableCell>{student.group}</TableCell>
              <TableCell>
                <span className="inline-flex flex-wrap items-center gap-1.5">
                  <LabProgressBadge progress={{ attempts: student.attempts, solved: student.solved }} />
                  {student.solved ? (
                    <span className="text-xs text-muted-foreground">{student.attempts} ta urinish</span>
                  ) : null}
                  {student.explanation ? <VerdictBadge verdict={student.explanation.verdict} /> : null}
                </span>
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {student.grade ? (
                  <span title={`${GRADE_SOURCE_LABELS[student.grade.source]}: ${student.grade.comment}`}>
                    {student.grade.score}
                  </span>
                ) : (
                  '—'
                )}
              </TableCell>
              <TableCell>{formatDateTime(student.last_attempt_at)}</TableCell>
              <TableCell className="text-right">
                {student.code || student.diagram ? (
                  <Button variant="outline" size="lg" onClick={() => setViewing(student)}>
                    {lab.kind === 'er' ? "Diagrammani ko'rish" : "Kodni ko'rish"}
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  const solved = progress.data?.filter((student) => student.solved).length

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Talabalar natijalari
          {progress.data?.length ? ` (${solved} / ${progress.data.length} bajargan)` : ''}
        </CardTitle>
        <CardDescription>Laboratoriya berilgan guruhlardagi barcha talabalar.</CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
      <Dialog open={Boolean(viewing)} onOpenChange={(open) => (!open ? setViewing(null) : undefined)}>
        <DialogContent className={lab.kind === 'er' ? 'max-h-[92svh] overflow-y-auto sm:max-w-5xl' : 'max-h-[92svh] overflow-y-auto sm:max-w-2xl'}>
          <DialogHeader>
            <DialogTitle>{viewing ? fullName(viewing) : ''}</DialogTitle>
            <DialogDescription>
              {viewing?.solved
                ? `Talabaning to'g'ri deb topilgan ${lab.kind === 'er' ? 'diagrammasi' : 'kodi'}.`
                : 'Talabaning oxirgi urinishi (hali bajarilmagan).'}
            </DialogDescription>
          </DialogHeader>
          {viewing?.grade ? (
            <div className="rounded-lg border bg-muted/40 p-3 text-sm">
              <div className="font-medium">
                {viewing.grade.score} / {MAX_SCORE} · {GRADE_SOURCE_LABELS[viewing.grade.source]}
              </div>
              {viewing.grade.comment ? (
                <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{viewing.grade.comment}</p>
              ) : null}
            </div>
          ) : null}
          {viewing?.diagram ? <ErEditor value={viewing.diagram} /> : viewing ? <SqlCode code={viewing.code} /> : null}
          {viewing?.explanation ? (
            <div className="grid gap-1.5 rounded-lg border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2 font-medium">
                Talabaning tushuntirishi <VerdictBadge verdict={viewing.explanation.verdict} />
              </div>
              <p className="whitespace-pre-wrap">{viewing.explanation.text}</p>
              <p className="text-xs whitespace-pre-wrap text-muted-foreground">AI: {viewing.explanation.feedback}</p>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </Card>
  )
}

function formatGap(minutes: number | null) {
  if (minutes === null) return '—'
  if (minutes < 60) return `${Math.round(minutes)} daqiqa`
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} soat`
  return `${Math.round(minutes / 60 / 24)} kun`
}

function SimilarWorkView({ work, kind }: { work: SimilarWork; kind: Lab['kind'] }) {
  return (
    <div className="grid min-w-0 content-start gap-2">
      <div className="text-sm">
        <span className="font-medium">{fullName(work)}</span>{' '}
        <span className="text-muted-foreground">
          · {work.group} · {work.solved ? 'bajargan' : 'bajarmagan'}
        </span>
      </div>
      {kind === 'er' && work.diagram ? <ErEditor value={work.diagram} /> : <SqlCode code={work.code} />}
    </div>
  )
}

function SimilarityCard({ lab }: { lab: Lab }) {
  const [viewing, setViewing] = useState<SimilarPair | null>(null)
  const report = useQuery({
    queryKey: ['lab-similarity', lab.id],
    queryFn: () => api<SimilarityReport>(`/labs/${lab.id}/similarity/`),
  })

  let content
  if (report.isPending) content = <ListSkeleton rows={2} />
  else if (report.isError) content = <ErrorState error={report.error} onRetry={() => void report.refetch()} />
  else if (!report.data.pairs.length)
    content = (
      <EmptyState
        icon={ShieldCheck}
        title="Shubhali o'xshash yechim topilmadi"
        description={`${report.data.compared} ta talaba yechimi solishtirildi.`}
      />
    )
  else
    content = (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Talabalar</TableHead>
            <TableHead className="text-right">O'xshashlik</TableHead>
            {lab.kind === 'sql' ? <TableHead className="text-right">Bir xil xato</TableHead> : null}
            <TableHead className="text-right">Yechimlar orasidagi vaqt</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {report.data.pairs.map((pair) => (
            <TableRow key={pair.students.map((student) => student.id).join('-')}>
              <TableCell>
                {pair.students.map((student) => (
                  <div key={student.id}>
                    <span className="font-medium">{fullName(student)}</span>{' '}
                    <span className="text-xs text-muted-foreground">{student.group}</span>
                  </div>
                ))}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {Math.round(pair.score * 100)}%
                <span className="block text-xs text-muted-foreground">{pair.shared} ta umumiy bo'lak</span>
              </TableCell>
              {lab.kind === 'sql' ? <TableCell className="text-right tabular-nums">{pair.shared_wrong || '—'}</TableCell> : null}
              <TableCell className="text-right tabular-nums">{formatGap(pair.gap_minutes)}</TableCell>
              <TableCell className="text-right">
                <Button variant="outline" size="lg" onClick={() => setViewing(pair)}>
                  Solishtirish
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle>O'xshash yechimlar{report.data?.pairs.length ? ` (${report.data.pairs.length})` : ''}</CardTitle>
        <CardDescription>
          Ko'chirish belgisi: namunaviy yechimda yo'q, talabaning o'zi tanlagan qismlar (nomlar, yozilish uslubi, izohlar)
          {lab.kind === 'sql' ? ' va bir xil noodatiy xato urinishlar' : ''} solishtiriladi. Bu dalil emas — ishlarni
          ko'rib, talabalar bilan gaplashib aniqlang.
        </CardDescription>
      </CardHeader>
      <CardContent>{content}</CardContent>
      <Dialog open={Boolean(viewing)} onOpenChange={(open) => (!open ? setViewing(null) : undefined)}>
        <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>Yechimlarni solishtirish</DialogTitle>
            <DialogDescription>
              {viewing
                ? `O'xshashlik ${Math.round(viewing.score * 100)}%${viewing.shared_wrong ? `, ${viewing.shared_wrong} ta bir xil xato urinish` : ''}.`
                : ''}
            </DialogDescription>
          </DialogHeader>
          {viewing ? (
            <div className="grid gap-4 md:grid-cols-2">
              {viewing.students.map((student) => (
                <SimilarWorkView key={student.id} work={student} kind={lab.kind} />
              ))}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </Card>
  )
}

function StaffView({ lab }: { lab: Lab }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { groups } = useGroupOptions()
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const duplicate = useMutation({
    mutationFn: () => api<Lab>(`/labs/${lab.id}/duplicate/`, { method: 'POST' }),
    onSuccess: (copy) => {
      toast.success('Nusxa yaratildi: endi uni tahrirlang')
      queryClient.setQueryData(['lab', copy.id], copy)
      void queryClient.invalidateQueries({ queryKey: ['labs'] })
      void navigate(`/labs/${copy.id}`)
    },
    onError: (error) => toast.error(errorMessage(error)),
  })

  const remove = useMutation({
    mutationFn: () => api(`/labs/${lab.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success("Laboratoriya o'chirildi")
      void queryClient.invalidateQueries({ queryKey: ['labs'] })
      void navigate('/labs', { replace: true })
    },
    onError: (error) => {
      toast.error(errorMessage(error))
      setConfirmingDelete(false)
    },
  })

  return (
    <>
      <BackLink />
      <PageHeader
        title={lab.title}
        description={`${fullName(lab.author)} · Guruhlar: ${groupNames(lab.groups, groups)}`}
        actions={
          <>
            <Button variant="outline" size="lg" onClick={() => setEditing(true)}>
              <Pencil aria-hidden="true" />
              Tahrirlash
            </Button>
            <Button variant="outline" size="lg" disabled={duplicate.isPending} onClick={() => duplicate.mutate()}>
              <Copy aria-hidden="true" />
              Nusxa olish
            </Button>
            <Button variant="destructive" size="lg" onClick={() => setConfirmingDelete(true)}>
              <Trash2 aria-hidden="true" />
              O'chirish
            </Button>
          </>
        }
      />
      <div className="grid gap-4">
        <ConditionCard lab={lab} />
        <GivenModelCard lab={lab} />
        {lab.kind === 'er' ? (
          <ErStaffCards lab={lab} />
        ) : lab.kind === 'norm' ? (
          <NormStaffCards lab={lab} />
        ) : (
          <SqlStaffCards lab={lab} />
        )}
        <ProgressCard lab={lab} />
        <MistakesCard lab={lab} />
        <SimilarityCard lab={lab} />
      </div>

      {editing ? <LabDialog lab={lab} onClose={() => setEditing(false)} /> : null}
      <ConfirmDialog
        open={confirmingDelete}
        title="Laboratoriyani o'chirish"
        description={`«${lab.title}» va unga tegishli barcha talabalar urinishlari o'chiriladi.`}
        confirmLabel="O'chirish"
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirmingDelete(false)}
      />
    </>
  )
}

function ErStaffCards({ lab }: { lab: Lab }) {
  const reference = lab.reference_diagram ?? { entities: [], relationships: [] }
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Namunaviy ER-diagramma</CardTitle>
          <CardDescription>Talabaga ko'rinmaydi. Talaba diagrammasi shu diagramma bilan solishtiriladi.</CardDescription>
        </CardHeader>
        <CardContent>
          <ErEditor value={reference} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Sinab ko'rish</CardTitle>
          <CardDescription>
            Namunani o'zgartirib, tekshiruv qanday xabar berishini ko'ring. Bu yerdagi tekshirishlar saqlanmaydi.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Laboratoriya tahrirlansa, muharrir yangi namuna bilan qayta ochiladi */}
          <ErLabRunner key={JSON.stringify(reference)} labId={lab.id} initialDiagram={reference} />
        </CardContent>
      </Card>
    </>
  )
}

function NormStaffCards({ lab }: { lab: Lab }) {
  const reference = lab.norm_reference
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Hisoblangan javob</CardTitle>
          <CardDescription>
            Talabaga ko'rinmaydi. Algoritm hisoblagan: talaba javobi xuddi shu algoritmlar bilan tekshiriladi, shuning
            uchun boshqa to'g'ri dekompozitsiya ham qabul qilinadi.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {reference ? (
            <div className="grid gap-1 font-mono text-sm">
              <div>Nomzod kalitlar: {reference.keys.map((key) => `{${key.join(', ')}}`).join('; ')}</div>
              <div>Hozirgi normal forma: {reference.normal_form}</div>
              <div>Dekompozitsiya:</div>
              <ul className="pl-4">
                {reference.decomposition.map((relation, index) => (
                  <li key={index}>
                    R{index + 1}({relation.join(', ')})
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>
      {lab.norm_task && reference ? (
        <Card>
          <CardHeader>
            <CardTitle>Sinab ko'rish</CardTitle>
            <CardDescription>Javobni o'zgartirib, tekshiruv qanday xabar berishini ko'ring. Saqlanmaydi.</CardDescription>
          </CardHeader>
          <CardContent>
            <NormLabRunner key={JSON.stringify(lab.norm_task)} labId={lab.id} task={lab.norm_task} initialAnswer={reference} />
          </CardContent>
        </Card>
      ) : null}
    </>
  )
}

function SqlStaffCards({ lab }: { lab: Lab }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Namunaviy yechim</CardTitle>
          <CardDescription>Talabaga ko'rinmaydi. Talaba natijasi shu kod natijasi bilan solishtiriladi.</CardDescription>
        </CardHeader>
        <CardContent>
          {lab.solution_sql?.trim() ? (
            <SqlCode code={lab.solution_sql.trim()} />
          ) : (
            <p className="text-sm text-muted-foreground">
              Kiritilmagan: xatosiz ishlagan har qanday kod to'g'ri hisoblanadi.
            </p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Sinab ko'rish</CardTitle>
          <CardDescription>
            Laboratoriyani talaba ko'rgandek tekshirib ko'ring. Bu yerdagi ishga tushirishlar saqlanmaydi.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Laboratoriya tahrirlansa, muharrir yangi namunaviy yechim bilan qayta ochiladi */}
          <LabRunner
            key={lab.solution_sql}
            labId={lab.id}
            initialCode={lab.solution_sql ?? ''}
            planAssistant={Boolean(lab.plan_query?.trim())}
            solved
          />
        </CardContent>
      </Card>
      {supportsGeneration(lab) ? <LabGenerateCard lab={lab} /> : null}
    </>
  )
}

// ---------- Talaba ----------

/** Laboratoriya murabbiyi kartasi (AI o'chirilgan guruhda ko'rsatilmaydi) */
function CoachCard({ labId, getWork }: { labId: number; getWork: () => LabWork }) {
  const user = useUser()
  if (!user.ai_enabled) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle>Murabbiy</CardTitle>
        <CardDescription>
          Savollar bilan yo'l ko'rsatadigan AI murabbiy. U namunaviy yechimni ko'rmaydi va tayyor javob bermaydi.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <LabCoach labId={labId} getWork={getWork} />
      </CardContent>
    </Card>
  )
}

/** Talablarni aniqlash: AI yoqilgan guruhda buyurtmachi bilan suhbat, nazorat guruhida to'liq talablar ro'yxati */
function InterviewCard({ lab }: { lab: Lab }) {
  if (!lab.interview) return null
  if (!lab.interview.ai) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Buyurtmachi talablari</CardTitle>
          <CardDescription>Buyurtmachi bilan kelishilgan talablar. Shular asosida ER-diagramma chizing.</CardDescription>
        </CardHeader>
        <CardContent>
          <RequirementList items={lab.interview.requirements ?? []} />
        </CardContent>
      </Card>
    )
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Buyurtmachi bilan suhbat</CardTitle>
        <CardDescription>
          Shartda talablar ro'yxati yo'q: ularni buyurtmachidan (AI) o'zingiz aniqlaysiz. U faqat so'ralgan narsani,
          texnik bo'lmagan tilda aytadi — kimlar va nimalar haqida ma'lumot saqlanishini, ular haqida nima yozilishini va
          ular qanday bog'langanini («bittami yoki bir nechta?») so'rang. Barcha {lab.interview.total} ta talabni
          aniqlashga harakat qiling.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <InterviewPanel labId={lab.id} />
      </CardContent>
    </Card>
  )
}

function StudentView({ lab }: { lab: Lab }) {
  const user = useUser()
  const queryClient = useQueryClient()
  const progress = lab.my_progress ?? { attempts: 0, solved: false }
  // Murabbiyga savol bilan yuboriladigan hozirgi ish: holat emas, ref — har bir harfda qayta chizilmasin
  const work = useRef<LabWork>({
    code: progress.last_code || lab.starter_sql || '',
    diagram: progress.last_diagram ?? null,
  })
  const getWork = () => work.current

  function handleResult(result: LabRunResult, work: { code?: string; diagram?: ErDiagram }) {
    // Holat va oxirgi ish keshda yangilanadi: sahifaga qaytilganda ham to'g'ri ko'rinadi
    queryClient.setQueryData<Lab>(['lab', lab.id], {
      ...lab,
      my_progress: {
        ...progress,
        attempts: progress.attempts + 1,
        solved: progress.solved || result.is_correct,
        grade: result.best_grade ?? progress.grade,
        last_code: work.code ?? '',
        last_diagram: work.diagram ?? null,
        last_fix: 'fix' in result ? result.fix : progress.last_fix,
      },
    })
    void queryClient.invalidateQueries({ queryKey: ['labs'] })
    // Yechilgandan keyin o'zaro baholash ochiladi
    if (result.is_correct && lab.kind === 'er') void queryClient.invalidateQueries({ queryKey: ['peer-review', lab.id] })
    // Yechilgandan keyin buyurtmachi suhbatida aniqlanmagan talablar ham ko'rsatiladi
    if (result.is_correct && lab.interview?.ai) void queryClient.invalidateQueries({ queryKey: ['lab-interview', lab.id] })
    // Normallashtirish javobi (last_answer) serverda tuzilma sifatida saqlanadi: qayta o'qib olinadi
    if (lab.kind === 'norm') void queryClient.invalidateQueries({ queryKey: ['lab', lab.id] })
  }

  if (lab.kind === 'er') {
    return (
      <>
        <BackLink />
        <PageHeader
          title={lab.title}
          description={`O'qituvchi: ${fullName(lab.author)}`}
          actions={<LabProgressBadge progress={progress} />}
        />
        <div className="grid gap-4">
          <ConditionCard lab={lab} />
          <InterviewCard lab={lab} />
          <Card>
            <CardHeader>
              <CardTitle>Mening ER-diagrammam</CardTitle>
              <CardDescription>
                Obyektlar, atributlar va bog'lanishlarni chizing. Xohlagancha tekshirish mumkin; tayyor bo'lgach
                baholashga topshiring.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ErLabRunner
                labId={lab.id}
                initialDiagram={progress.last_diagram}
                initialFix={progress.last_fix}
                gradable
                onResult={(result, diagram) => handleResult(result, { diagram })}
                onDiagramChange={(diagram) => (work.current = { diagram })}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>O'zaro baholash</CardTitle>
              <CardDescription>
                Laboratoriyani to'g'ri yechgach, guruhdoshlaringizning diagrammalarini rubrika bo'yicha baholang. Ikkala
                tomon ham bir-birining ismini ko'rmaydi.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PeerReviewPanel labId={lab.id} />
            </CardContent>
          </Card>
          <CoachCard labId={lab.id} getWork={getWork} />
        </div>
      </>
    )
  }

  if (lab.kind === 'norm' && lab.norm_task) {
    return (
      <>
        <BackLink />
        <PageHeader
          title={lab.title}
          description={`O'qituvchi: ${fullName(lab.author)}`}
          actions={<LabProgressBadge progress={progress} />}
        />
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <ConditionCard lab={lab} />
          <Card>
            <CardHeader>
              <CardTitle>Mening javobim</CardTitle>
              <CardDescription>
                Funksional bog'liqliklar bo'yicha kalitlarni, normal formani va dekompozitsiyani toping. Javob hisoblab
                tekshiriladi: boshqa to'g'ri dekompozitsiya ham qabul qilinadi.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <NormLabRunner
                labId={lab.id}
                task={lab.norm_task}
                initialAnswer={progress.last_answer}
                gradable
                onResult={(result, code) => handleResult(result, { code })}
                onAnswerChange={(code) => (work.current = { code })}
              />
            </CardContent>
          </Card>
        </div>
        <div className="mt-4">
          <CoachCard labId={lab.id} getWork={getWork} />
        </div>
      </>
    )
  }

  return (
    <>
      <BackLink />
      <PageHeader
        title={lab.title}
        description={`O'qituvchi: ${fullName(lab.author)}`}
        actions={<LabProgressBadge progress={progress} />}
      />
      <GivenModelCard lab={lab} />
      <div className={cn('grid items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]', lab.given_diagram?.entities.length && 'mt-4')}>
        <ConditionCard lab={lab} />
        <Card>
          <CardHeader>
            <CardTitle>Mening kodim</CardTitle>
            <CardDescription>
              Kodni yozib, ishga tushiring. Xohlagancha urinish mumkin; tayyor bo'lgach baholashga topshiring.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LabRunner
              labId={lab.id}
              initialCode={lab.my_progress?.last_code || lab.starter_sql || ''}
              gradable
              onResult={(result, code) => handleResult(result, { code })}
              planAssistant={Boolean(lab.plan_query?.trim()) && user.ai_enabled}
              solved={progress.solved}
              onCodeChange={(code) => (work.current = { code })}
            />
          </CardContent>
        </Card>
      </div>
      <div className="mt-4">
        <CoachCard labId={lab.id} getWork={getWork} />
      </div>
    </>
  )
}

export function LabDetailPage() {
  const user = useUser()
  const params = useParams()
  const id = Number(params.id)
  const validId = Number.isInteger(id) && id > 0

  const lab = useQuery({
    queryKey: ['lab', id],
    queryFn: () => api<Lab>(`/labs/${id}/`),
    enabled: validId,
  })

  if (!validId) return <NotFoundPage />
  if (lab.isPending) return <ListSkeleton />
  if (lab.isError) {
    if (lab.error instanceof ApiError && lab.error.status === 404) return <NotFoundPage />
    return <ErrorState error={lab.error} onRetry={() => void lab.refetch()} />
  }

  return user.role === 'student' ? <StudentView key={id} lab={lab.data} /> : <StaffView key={id} lab={lab.data} />
}
