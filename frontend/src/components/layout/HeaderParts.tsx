// Sarlavha qismlari NiceAdmin "header-nav" uslubida: logo, sahifa qidiruvi, bildirishnomalar va profil menyusi.
import { Bell, ChevronDown, Database, LogOut, Search, UserRound } from 'lucide-react'
import { useId, useMemo, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { fullName, useAuth, useUser } from '@/lib/auth'
import { timeAgo, useDashboard } from '@/lib/dashboard'
import { navItemsFor } from '@/lib/nav'
import { ROLE_LABELS, type DashboardTone } from '@/lib/types'
import { cn } from '@/lib/utils'

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2 rounded-md outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
      <span className="brand-gradient flex size-8 shrink-0 items-center justify-center rounded-md text-white">
        <Database className="size-4.5" aria-hidden="true" />
      </span>
      {/* Telefonda sarlavhada faqat belgi: joy qidiruv va menyular uchun */}
      <span
        className={cn(
          'font-heading text-xl font-bold text-heading sm:text-[1.625rem] sm:leading-none',
          compact ? 'sm:text-xl' : 'hidden min-[480px]:inline',
        )}
      >
        MB loyihalash
      </span>
    </Link>
  )
}

/** Menyudagi sahifalar bo'yicha tez qidiruv: Enter — birinchi mos sahifaga o'tish. */
export function HeaderSearch({ className }: { className?: string }) {
  const user = useUser()
  const navigate = useNavigate()
  const listId = useId()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)

  const results = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('uz')
    if (!needle) return []
    return navItemsFor(user.role).filter((item) => item.label.toLocaleLowerCase('uz').includes(needle))
  }, [query, user.role])

  function go(index: number) {
    const item = results[index]
    if (!item) return
    navigate(item.to)
    setQuery('')
    setOpen(false)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    go(active)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((value) => Math.min(value + 1, results.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((value) => Math.max(value - 1, 0))
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && query.trim() !== ''
  return (
    <form role="search" onSubmit={onSubmit} className={cn('relative', className)}>
      <label htmlFor={`${listId}-input`} className="sr-only">
        Sahifa qidirish
      </label>
      <input
        id={`${listId}-input`}
        type="search"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        placeholder="Sahifa qidirish..."
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setActive(0)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className="h-9 w-full rounded-[3px] border border-[rgb(1_41_112/20%)] bg-card pr-9 pl-3 text-sm text-heading transition-shadow outline-none placeholder:text-muted-foreground hover:border-[rgb(1_41_112/30%)] focus:border-[rgb(1_41_112/30%)] focus:shadow-[0_0_10px_0_rgb(1_41_112/15%)] dark:border-input"
      />
      <button
        type="submit"
        className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-heading"
        aria-label="Qidirish"
      >
        <Search className="size-4" aria-hidden="true" />
      </button>
      {showList ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute inset-x-0 top-full z-50 mt-1 overflow-hidden rounded-md bg-popover py-1 shadow-(--card-shadow) ring-1 ring-border"
        >
          {results.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">Mos sahifa topilmadi</li>
          ) : (
            results.map((item, index) => (
              <li
                key={item.to}
                role="option"
                aria-selected={index === active}
                // onMouseDown: input fokusni yo'qotib ro'yxat yopilishidan oldin
                onMouseDown={(event) => {
                  event.preventDefault()
                  go(index)
                }}
                className={cn(
                  'flex cursor-pointer items-center gap-2 px-3 py-2 text-sm text-heading',
                  index === active && 'bg-accent text-primary',
                )}
              >
                <item.icon className="size-4 text-muted-foreground" aria-hidden="true" />
                {item.label}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </form>
  )
}

const TONE_ICON: Record<DashboardTone, string> = {
  primary: 'text-primary',
  info: 'text-tone-blue',
  success: 'text-tone-green',
  warning: 'text-tone-orange',
  danger: 'text-destructive',
}

/** Bildirishnomalar: bazadagi haqiqiy holatdan (yaqin muddatlar, qaytarilgan va tekshirilmagan ishlar). */
export function NotificationsMenu() {
  const { data, isPending, isError } = useDashboard()
  const alerts = data?.alerts ?? []
  const count = alerts.length
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="relative flex size-10 items-center justify-center rounded-md text-heading outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
        aria-label={count ? `Bildirishnomalar: ${count} ta` : 'Bildirishnomalar'}
      >
        <Bell className="size-5" aria-hidden="true" />
        {count ? (
          <span className="absolute top-1 right-0.5 min-w-4 rounded-full bg-primary px-1 text-[0.625rem] leading-4 font-semibold text-primary-foreground">
            {count}
          </span>
        ) : null}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-w-[calc(100vw-2rem)] p-0">
        <DropdownMenuLabel className="border-b px-4 py-3 text-center text-sm font-normal text-heading">
          {isPending
            ? 'Yuklanmoqda...'
            : isError
              ? "Bildirishnomalarni olib bo'lmadi"
              : count
                ? `Sizda ${count} ta bildirishnoma bor`
                : "Yangi bildirishnoma yo'q"}
        </DropdownMenuLabel>
        <div className="max-h-96 overflow-y-auto">
          {alerts.map((alert, index) => (
            <DropdownMenuItem key={`${alert.link}-${index}`} asChild className="rounded-none border-b px-4 py-3 last:border-b-0">
              <Link to={alert.link} className="flex items-start gap-3">
                <Bell className={cn('mt-0.5 size-4 shrink-0', TONE_ICON[alert.tone])} aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block truncate font-medium text-heading">{alert.title}</span>
                  <span className="block text-xs text-muted-foreground">{alert.text}</span>
                  <span className="block text-xs text-muted-foreground">{timeAgo(alert.at)}</span>
                </span>
              </Link>
            </DropdownMenuItem>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function initials(person: { first_name: string; last_name: string; username: string }) {
  const text = `${person.first_name.charAt(0)}${person.last_name.charAt(0)}`.trim()
  return (text || person.username.slice(0, 2)).toLocaleUpperCase('uz')
}

/** Profil menyusi: ism, rol, profil sahifasi va chiqish. */
export function ProfileMenu() {
  const user = useUser()
  const { logout } = useAuth()
  const name = fullName(user)
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex items-center gap-2 rounded-md py-1 pr-1 pl-1 text-heading outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 sm:pr-2"
        aria-label={`Profil menyusi: ${name}`}
      >
        <span className="brand-gradient flex size-9 items-center justify-center rounded-full text-xs font-semibold text-white">
          {initials(user)}
        </span>
        <span className="hidden max-w-40 truncate text-sm font-semibold xl:block">{name}</span>
        <ChevronDown className="hidden size-4 xl:block" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="py-2 text-center">
          <span className="block font-heading text-lg font-semibold text-heading">{name}</span>
          <span className="block text-xs font-normal text-muted-foreground">
            {ROLE_LABELS[user.role]} · {user.username}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="py-2">
          <Link to="/profile">
            <UserRound aria-hidden="true" />
            Mening profilim
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="py-2" onSelect={() => void logout()}>
          <LogOut aria-hidden="true" />
          Chiqish
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
