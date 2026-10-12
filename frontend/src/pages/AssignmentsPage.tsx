import { useQuery } from '@tanstack/react-query'
import { CalendarClock, ClipboardList, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { AssignmentDialog } from '@/components/AssignmentDialog'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/States'
import { DeadlineBadge } from '@/components/SubmissionBadges'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { fullName, useUser } from '@/lib/auth'
import { formatDateTime } from '@/lib/format'
import { groupNames, useGroupOptions } from '@/lib/groups'
import type { Assignment } from '@/lib/types'

export function AssignmentsPage() {
  const user = useUser()
  const isStaff = user.role !== 'student'
  const { groups } = useGroupOptions()
  const [creating, setCreating] = useState(false)

  const assignments = useQuery({ queryKey: ['assignments'], queryFn: () => api<Assignment[]>('/assignments/') })

  const addButton = isStaff ? (
    <Button size="lg" onClick={() => setCreating(true)}>
      <Plus aria-hidden="true" />
      Topshiriq qo'shish
    </Button>
  ) : null

  let content
  if (assignments.isPending) {
    content = <ListSkeleton />
  } else if (assignments.isError) {
    content = <ErrorState error={assignments.error} onRetry={() => void assignments.refetch()} />
  } else if (!assignments.data.length) {
    content = (
      <EmptyState
        icon={ClipboardList}
        title="Hali topshiriq yo'q"
        description={
          isStaff
            ? 'Guruhlaringiz uchun birinchi topshiriqni yarating.'
            : user.group
              ? "O'qituvchi topshiriq berganda shu yerda ko'rinadi."
              : 'Siz hali guruhga biriktirilmagansiz. Administratorga murojaat qiling.'
        }
        action={addButton}
      />
    )
  } else {
    content = (
      <ul className="grid gap-3">
        {assignments.data.map((assignment) => (
          <li key={assignment.id}>
            <Link
              to={`/assignments/${assignment.id}`}
              className="block rounded-xl border bg-card p-4 transition-colors outline-none hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h2 className="min-w-0 font-medium">{assignment.title}</h2>
                <DeadlineBadge deadline={assignment.deadline} />
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{assignment.description}</p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <CalendarClock className="size-3.5" aria-hidden="true" />
                  Muddat: {formatDateTime(assignment.deadline)}
                </span>
                <span>{fullName(assignment.author)}</span>
                {isStaff ? <span>Guruhlar: {groupNames(assignment.groups, groups)}</span> : null}
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
        title="Topshiriqlar"
        description={isStaff ? 'Topshiriqlar va ularga kelgan yechimlar.' : 'Guruhingizga berilgan topshiriqlar.'}
        actions={assignments.data?.length ? addButton : null}
      />
      {content}
      {creating ? <AssignmentDialog onClose={() => setCreating(false)} /> : null}
    </>
  )
}
