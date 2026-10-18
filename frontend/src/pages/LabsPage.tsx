import { useQuery } from '@tanstack/react-query'
import { Download, FlaskConical, Layers, Lock, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { LabDialog } from '@/components/LabDialog'
import { LabLevelBadge } from '@/components/LabLevel'
import { ModulesDialog } from '@/components/ModulesDialog'
import { LearningPathCard } from '@/components/LearningPath'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api, errorMessage } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { downloadFile } from '@/lib/download'
import { groupNames, useGroupOptions } from '@/lib/groups'
import { MAX_SCORE, type Lab, type LabModuleShort, type LabProgress } from '@/lib/types'

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

interface ModuleSection {
  module: LabModuleShort | null
  labs: Lab[]
}

/** Modullar tartib raqami bo'yicha, ichida laboratoriyalar soddadan murakkabga; modulsizlar oxirida */
function byModule(labs: Lab[]): ModuleSection[] {
  const sections = new Map<number, ModuleSection>()
  const free: Lab[] = []
  for (const lab of labs) {
    if (!lab.module_detail) {
      free.push(lab)
      continue
    }
    const section = sections.get(lab.module_detail.id) ?? { module: lab.module_detail, labs: [] }
    section.labs.push(lab)
    sections.set(lab.module_detail.id, section)
  }
  const result = [...sections.values()].sort(
    (a, b) => a.module!.order - b.module!.order || a.module!.id - b.module!.id,
  )
  for (const section of result) section.labs.sort((a, b) => a.position - b.position || a.id - b.id)
  if (free.length) result.push({ module: null, labs: free })
  return result
}

function LabCard({ lab, isStaff, groupsText }: { lab: Lab; isStaff: boolean; groupsText: string }) {
  const header = (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <h2 className="min-w-0 font-medium">
        {lab.module_detail && lab.position ? <span className="mr-1 text-muted-foreground tabular-nums">{lab.position}.</span> : null}
        {lab.title}
        {lab.kind !== 'sql' ? (
          <Badge variant="outline" className="ml-2 align-middle">
            {lab.kind === 'er' ? 'ER-diagramma' : 'Normallashtirish'}
          </Badge>
        ) : null}
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        {lab.level ? <LabLevelBadge level={lab.level} /> : null}
        {lab.locked ? (
          <Badge variant="outline">
            <Lock aria-hidden="true" />
            Yopiq
          </Badge>
        ) : lab.my_progress ? (
          <LabProgressBadge progress={lab.my_progress} />
        ) : null}
      </div>
    </div>
  )

  if (lab.locked) {
    return (
      <div className="rounded-xl border border-dashed bg-muted/30 p-4" aria-disabled="true">
        {header}
        <p className="mt-1 text-sm text-muted-foreground">
          Avval{' '}
          {lab.blocked_by ? (
            <Link to={`/labs/${lab.blocked_by.id}`} className="font-medium text-foreground underline underline-offset-4">
              «{lab.blocked_by.title}»
            </Link>
          ) : (
            'oldingi laboratoriyani'
          )}{' '}
          laboratoriyasini yeching, shundan keyin bu laboratoriya ochiladi.
        </p>
      </div>
    )
  }

  return (
    <Link
      to={`/labs/${lab.id}`}
      className="block rounded-xl border bg-card p-4 transition-colors outline-none hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      {header}
      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{lab.description}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>{fullName(lab.author)}</span>
        {isStaff ? <span>Guruhlar: {groupsText}</span> : null}
      </div>
    </Link>
  )
}

export function LabsPage() {
  const user = useUser()
  const isStaff = user.role !== 'student'
  const { groups } = useGroupOptions()
  const [creating, setCreating] = useState(false)
  const [managingModules, setManagingModules] = useState(false)

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
    const sections = byModule(labs.data)
    const hasModules = sections.some((section) => section.module)
    content = (
      <div className="grid gap-6">
        {sections.map((section) => {
          const solved = section.labs.filter((lab) => lab.my_progress?.solved).length
          return (
            <section key={section.module?.id ?? 'free'} aria-labelledby={`module-${section.module?.id ?? 'free'}`} className="grid gap-3">
              {hasModules ? (
                <div>
                  <h2 id={`module-${section.module?.id ?? 'free'}`} className="flex flex-wrap items-center gap-2 text-base font-semibold">
                    {section.module ? section.module.title : 'Boshqa laboratoriyalar'}
                    {section.module?.sequential ? <Badge variant="secondary">Ketma-ket</Badge> : null}
                    {!isStaff && section.module ? (
                      <span className="text-sm font-normal text-muted-foreground tabular-nums">
                        {solved} / {section.labs.length} bajarilgan
                      </span>
                    ) : null}
                  </h2>
                  {section.module?.description ? (
                    <p className="mt-0.5 text-sm text-muted-foreground">{section.module.description}</p>
                  ) : null}
                </div>
              ) : null}
              <ul className="grid gap-3">
                {section.labs.map((lab) => (
                  <li key={lab.id}>
                    <LabCard lab={lab} isStaff={isStaff} groupsText={isStaff ? groupNames(lab.groups, groups) : ''} />
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>
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
              <Button size="lg" variant="outline" onClick={() => setManagingModules(true)}>
                <Layers aria-hidden="true" />
                Modullar
              </Button>
              {addButton}
            </>
          ) : null
        }
      />
      {isStaff ? null : <LearningPathCard />}
      {content}
      {creating ? <LabDialog onClose={() => setCreating(false)} /> : null}
      {managingModules && labs.data ? <ModulesDialog labs={labs.data} onClose={() => setManagingModules(false)} /> : null}
    </>
  )
}
