// Sahifa karkasi NiceAdmin (BootstrapMade) shabloni asosida: yuqorida qat'iy sarlavha, chapda oq yon menyu,
// pastda footer. Kompyuterda menyu tugma bilan yashiriladi, telefon va planshetda chiqib keladigan panel.
import { Menu } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useNavigation } from 'react-router-dom'

import { AppearanceMenu } from '@/components/AppearanceMenu'
import { ConsentPrompt } from '@/components/Consent'
import { HeaderSearch, Logo, NotificationsMenu, ProfileMenu } from '@/components/layout/HeaderParts'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { useUser } from '@/lib/auth'
import { navSectionsFor } from '@/lib/nav'
import { cn } from '@/lib/utils'

const SIDEBAR_KEY = 'mb-sidebar-hidden'
const YEAR = new Date().getFullYear()

function readHidden() {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === '1'
  } catch {
    return false
  }
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const user = useUser()
  return (
    <nav aria-label="Asosiy menyu">
      <ul className="flex flex-col">
        {navSectionsFor(user.role).map((section, index) => (
          <li key={section.heading ?? index}>
            {section.heading ? (
              <div className="mt-2.5 mb-1.5 ml-[15px] text-[0.6875rem] font-semibold tracking-wide text-sidebar-muted uppercase">
                {section.heading}
              </div>
            ) : null}
            <ul className="flex flex-col gap-[5px]">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'group flex items-center gap-2.5 rounded-[4px] px-[15px] py-2.5 text-[0.9375rem] font-semibold transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-sidebar-ring',
                        isActive
                          ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                          : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <item.icon
                          className={cn(
                            'size-4 shrink-0',
                            isActive ? 'text-sidebar-accent-foreground' : 'text-sidebar-muted group-hover:text-sidebar-accent-foreground',
                          )}
                          aria-hidden="true"
                        />
                        {item.label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
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

function Footer() {
  return (
    <footer className="border-t border-[#cddfff] px-5 py-6 text-center text-[0.8125rem] text-heading transition-[margin] dark:border-border">
      <div>
        © {YEAR} <strong className="font-semibold">MB loyihalash</strong> — ma'lumotlar bazasini
        loyihalash ta'lim platformasi
      </div>
      {/* NiceAdmin bepul litsenziyasi muallif havolasini saqlashni talab qiladi */}
      <div className="mt-1 text-xs text-muted-foreground">
        Dizayn:{' '}
        <a
          href="https://bootstrapmade.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          BootstrapMade
        </a>{' '}
        (NiceAdmin)
      </div>
    </footer>
  )
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [hidden, setHidden] = useState(readHidden)

  function toggleSidebar() {
    if (window.matchMedia('(min-width: 1200px)').matches) {
      const next = !hidden
      setHidden(next)
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? '1' : '0')
      } catch {
        // Saqlash taqiqlangan: tanlov shu oynada amal qiladi
      }
    } else {
      setMenuOpen(true)
    }
  }

  return (
    <div className="min-h-svh bg-page">
      <header className="fixed inset-x-0 top-0 z-40 flex h-15 items-center bg-card pr-2 pl-4 shadow-(--header-shadow) sm:pl-5 sm:pr-4">
        <div className="flex min-w-0 items-center gap-2 nice:w-[280px] nice:shrink-0">
          <Logo />
        </div>
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={hidden ? "Yon menyuni ko'rsatish" : 'Yon menyuni yashirish'}
          aria-expanded={menuOpen || undefined}
          className="ml-1 flex size-10 shrink-0 items-center justify-center rounded-md text-heading outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 sm:ml-2.5"
        >
          <Menu className="size-7" aria-hidden="true" />
        </button>
        <HeaderSearch className="ml-4 hidden w-[min(360px,28vw)] lg:block" />

        <div className="ml-auto flex items-center gap-0.5 sm:gap-1.5">
          <AppearanceMenu />
          <NotificationsMenu />
          <ProfileMenu />
        </div>
        <NavigationProgress />
      </header>

      {/* Kompyuter (≥1200px): doimiy yon menyu */}
      <aside
        className={cn(
          'fixed top-15 bottom-0 left-0 z-30 hidden w-[300px] overflow-y-auto bg-sidebar p-5 shadow-(--header-shadow) transition-transform [scrollbar-color:#aab7cf_transparent] [scrollbar-width:thin] nice:block',
          hidden && '-translate-x-full',
        )}
        aria-hidden={hidden || undefined}
        inert={hidden || undefined}
      >
        <NavList />
      </aside>

      {/* Telefon va planshet: chiqib keladigan menyu */}
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-[300px] gap-0 overflow-y-auto border-none bg-sidebar p-5 text-sidebar-foreground">
          <SheetHeader className="mb-4 p-0">
            <SheetTitle className="sr-only">Menyu</SheetTitle>
            <SheetDescription className="sr-only">Sahifalar ro'yxati</SheetDescription>
            <Logo compact />
          </SheetHeader>
          <HeaderSearch className="mb-4 lg:hidden" />
          <NavList onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className={cn('flex min-h-svh flex-col pt-15 transition-[margin]', !hidden && 'nice:ml-[300px]')}>
        <main className="w-full flex-1 px-4 py-5 sm:px-5 nice:px-[30px]">
          <Outlet />
        </main>
        <Footer />
        <ConsentPrompt />
      </div>
    </div>
  )
}
