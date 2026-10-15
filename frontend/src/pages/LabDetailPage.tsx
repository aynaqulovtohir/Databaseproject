import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Pencil, Trash2, Users } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErEditor } from '@/components/ErEditor'
import { ErLabRunner } from '@/components/ErLabRunner'
import { LabDialog } from '@/components/LabDialog'
import { LabRunner } from '@/components/LabRunner'
import { PageHeader } from '@/components/PageHeader'
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
import {
  GRADE_SOURCE_LABELS,
  MAX_SCORE,
  type ErDiagram,
  type Lab,
  type LabRunResult,
  type LabStudentProgress,
} from '@/lib/types'
import { LabProgressBadge } from '@/pages/LabsPage'
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

function ConditionCard({ lab }: { lab: Lab }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Laboratoriya sharti</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <p className="text-sm whitespace-pre-wrap">{lab.description}</p>
        {lab.kind === 'er' ? null : lab.setup_sql.trim() ? (
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
            <Button variant="destructive" size="lg" onClick={() => setConfirmingDelete(true)}>
              <Trash2 aria-hidden="true" />
              O'chirish
            </Button>
          </>
        }
      />
      <div className="grid gap-4">
        <ConditionCard lab={lab} />
        {lab.kind === 'er' ? <ErStaffCards lab={lab} /> : <SqlStaffCards lab={lab} />}
        <ProgressCard lab={lab} />
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
          <LabRunner key={lab.solution_sql} labId={lab.id} initialCode={lab.solution_sql ?? ''} />
        </CardContent>
      </Card>
    </>
  )
}

// ---------- Talaba ----------

function StudentView({ lab }: { lab: Lab }) {
  const queryClient = useQueryClient()
  const progress = lab.my_progress ?? { attempts: 0, solved: false }

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
              />
            </CardContent>
          </Card>
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
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
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
              initialCode={lab.my_progress?.last_code ?? ''}
              gradable
              onResult={(result, code) => handleResult(result, { code })}
            />
          </CardContent>
        </Card>
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
