import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { useAuth } from '@/lib/auth'
import { navItemForPath } from '@/lib/nav'
import { t } from '@/lib/i18n'

interface PageHeaderProps {
  title: string
  description?: string
  /** O'ng tomonda turadigan tugmalar */
  actions?: ReactNode
}

/** NiceAdmin "breadcrumb": Bosh sahifa / bo'lim / joriy sahifa. Kirmagan foydalanuvchida (ekspert havolasi) ko'rsatilmaydi. */
function Breadcrumbs({ title }: { title: string }) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  if (!user) return null
  const section = navItemForPath(user.role, pathname)
  const crumbs: { label: string; to?: string }[] = [{ label: t('Bosh sahifa'), to: pathname === '/' ? undefined : '/' }]
  if (section) {
    const onSection = pathname === section.to
    crumbs.push({ label: section.label, to: onSection ? undefined : section.to })
    if (!onSection) crumbs.push({ label: title })
  }
  return (
    <nav aria-label={t('Joylashuv')} className="mt-1">
      <ol className="flex flex-wrap items-center gap-1 font-heading text-sm font-semibold text-muted-foreground">
        {crumbs.map((crumb, index) => (
          <li key={index} className="flex min-w-0 items-center gap-1">
            {index > 0 ? <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" /> : null}
            {crumb.to ? (
              <Link to={crumb.to} className="transition-colors hover:text-heading">
                {crumb.label}
              </Link>
            ) : (
              <span aria-current="page" className="truncate text-[#51678f] dark:text-foreground">
                {crumb.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-heading text-2xl font-semibold text-heading">{title}</h1>
          <Breadcrumbs title={title} />
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      {description ? <p className="mt-2 text-sm text-muted-foreground">{description}</p> : null}
    </div>
  )
}
