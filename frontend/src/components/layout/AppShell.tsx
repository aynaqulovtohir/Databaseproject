import { Database, LogOut, Menu } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useNavigation } from 'react-router-dom'

import { ConsentPrompt } from '@/components/Consent'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { fullName, useAuth, useUser } from '@/lib/auth'
import { navItemsFor } from '@/lib/nav'
import { ROLE_LABELS } from '@/lib/types'
import { cn } from '@/lib/utils'

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Database className="size-5" aria-hidden="true" />
      </div>
      <div className="leading-tight">
        <div className="text-sm font-semibold">MB loyihalash</div>
        <div className="text-xs text-muted-foreground">Ta'lim platformasi</div>
      </div>
    </div>
  )
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const user = useUser()
  return (
    <nav className="flex flex-col gap-1" aria-label="Asosiy menyu">
      {navItemsFor(user.role).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )
          }
        >
          <item.icon className="size-4 shrink-0" aria-hidden="true" />
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

/** Keyingi sahifaning kodi yuklanayotganini bildiradi (sahifalar alohida bo'laklarda). */
function NavigationProgress() {
  const navigation = useNavigation()
  if (navigation.state === 'idle') return null
  return (
    <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden" role="progressbar" aria-label="Sahifa yuklanmoqda">
      <div className="h-full w-1/3 animate-pulse bg-primary" />
    </div>
  )
}

export function AppShell() {
  const user = useUser()
  const { logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex min-h-svh bg-muted/40">
      {/* Kompyuter: doimiy yon menyu */}
      <aside className="sticky top-0 hidden h-svh w-64 shrink-0 flex-col gap-6 border-r bg-background p-4 lg:flex">
        <Brand />
        <NavList />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur lg:px-6">
          {/* Telefon: yig'iladigan menyu */}
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon-lg" className="lg:hidden" aria-label="Menyuni ochish">
                <Menu className="size-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 gap-6 p-4">
              <SheetHeader className="p-0">
                <SheetTitle className="sr-only">Menyu</SheetTitle>
                <SheetDescription className="sr-only">Sahifalar ro'yxati</SheetDescription>
                <Brand />
              </SheetHeader>
              <NavList onNavigate={() => setMenuOpen(false)} />
            </SheetContent>
          </Sheet>

          <div className="ml-auto flex min-w-0 items-center gap-3">
            <div className="min-w-0 text-right leading-tight">
              <div className="truncate text-sm font-medium">{fullName(user)}</div>
              <div className="hidden text-xs text-muted-foreground sm:block">{user.username}</div>
            </div>
            <Badge variant="secondary">{ROLE_LABELS[user.role]}</Badge>
            <Button variant="outline" size="lg" onClick={() => void logout()}>
              <LogOut aria-hidden="true" />
              <span className="hidden sm:inline">Chiqish</span>
              <span className="sr-only sm:hidden">Chiqish</span>
            </Button>
          </div>
          <NavigationProgress />
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
        <ConsentPrompt />
      </div>
    </div>
  )
}
