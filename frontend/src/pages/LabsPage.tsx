import { useQuery } from '@tanstack/react-query'
import { Download, FlaskConical, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { LabDialog } from '@/components/LabDialog'
import { LearningPathCard } from '@/components/LearningPath'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api, errorMessage } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { downloadFile } from '@/lib/download'
import { groupNames, useGroupOptions } from '@/lib/groups'
import { MAX_SCORE, type Lab, type LabProgress } from '@/lib/types'

export function LabProgressBadge({ progress }: { progress: Pick<LabProgress, 'attempts' | 'solved' | 'grade'> }) {
  if (progress.grade) {
    return (
      <Badge className="bg-emerald-100 text-emerald-800 tabular-nums">
        Baho: {progress.grade.score} / {MAX_SCORE}
      </Badge>
    )
  }
  if (progress.solved) return <Badge className="bg-emerald-100 text-emerald-800">Bajarilgan</Badge>
  if (progress.attempts) return <Badge className="bg-amber-100 text-amber-800">{progress.attempts} ta urinish</Badge>
  return <Badge variant="outline">Boshlanmagan</Badge>
}

/** Ilmiy tadqiqot uchun anonim ma'lumotlar: urinishlar, xato turlari va baholar (ZIP ichida CSV) */
function ResearchExportButton() {
  const [downloading, setDownloading] = useState(false)

  async function download() {
    setDownloading(true)
    try {
      const today = new Date().toLocaleDateString('sv')
      await downloadFile('/labs/research-export/', `laboratoriya-tadqiqot-${today}.zip`)
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <Button
      size="lg"
      variant="outline"
      disabled={downloading}
      onClick={() => void download()}
      title="Anonim ma'lumotlar: talaba ismi va kodi kirmaydi"
    >
      <Download aria-hidden="true" />
      {downloading ? 'Tayyorlanmoqda…' : "Tadqiqot ma'lumotlari"}
    </Button>
  )
}

export function LabsPage() {
  const user = useUser()
  const isStaff = user.role !== 'student'
  const { groups } = useGroupOptions()
  const [creating, setCreating] = useState(false)

  const labs = useQuery({ queryKey: ['labs'], queryFn: () => api<Lab[]>('/labs/') })

  const addButton = isStaff ? (
    <Button size="lg" onClick={() => setCreating(true)}>
      <Plus aria-hidden="true" />
      Laboratoriya qo'shish
    </Button>
  ) : null

  let content
  if (labs.isPending) {
    content = <ListSkeleton />
  } else if (labs.isError) {
    content = <ErrorState error={labs.error} onRetry={() => void labs.refetch()} />
  } else if (!labs.data.length) {
    content = (
      <EmptyState
        icon={FlaskConical}
        title="Hali laboratoriya yo'q"
        description={
          isStaff
            ? 'Guruhlaringiz uchun birinchi SQL laboratoriyasini yarating.'
            : user.group
              ? "O'qituvchi laboratoriya qo'shganda shu yerda ko'rinadi."
              : 'Siz hali guruhga biriktirilmagansiz. Administratorga murojaat qiling.'
        }
        action={addButton}
      />
    )
  } else {
    content = (
      <ul className="grid gap-3">
        {labs.data.map((lab) => (
          <li key={lab.id}>
            <Link
              to={`/labs/${lab.id}`}
              className="block rounded-xl border bg-card p-4 transition-colors outline-none hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="min-w-0 font-medium">
                  {lab.title}
                  {lab.kind !== 'sql' ? (
                    <Badge variant="outline" className="ml-2 align-middle">
                      {lab.kind === 'er' ? 'ER-diagramma' : 'Normallashtirish'}
                    </Badge>
                  ) : null}
                </h2>
                {lab.my_progress ? <LabProgressBadge progress={lab.my_progress} /> : null}
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{lab.description}</p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{fullName(lab.author)}</span>
                {isStaff ? <span>Guruhlar: {groupNames(lab.groups, groups)}</span> : null}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <>
      <PageHeader
        title="Virtual laboratoriya"
        description={
          isStaff
            ? 'SQL laboratoriyalari va talabalar natijalari.'
            : "SQL kod yozing va ishga tushiring: to'g'ri bo'lsa yashil, xato bo'lsa maslahat chiqadi."
        }
        actions={
          isStaff && labs.data?.length ? (
            <>
              <ResearchExportButton />
              {addButton}
            </>
          ) : null
        }
      />
      {isStaff ? null : <LearningPathCard />}
      {content}
      {creating ? <LabDialog onClose={() => setCreating(false)} /> : null}
    </>
  )
}
