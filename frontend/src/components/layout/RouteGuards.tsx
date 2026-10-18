import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'
import type { Role } from '@/lib/types'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export function FullPageLoader() {
  return (
    <div className="flex min-h-svh items-center justify-center" role="status" aria-label="Yuklanmoqda">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
    </div>
  )
}

/** Sessiya tekshirilguncha kutadi; kirmagan foydalanuvchini login sahifasiga yuboradi. */
export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <FullPageLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <AppShell />
}

/** Sahifani faqat ko'rsatilgan rollarga ochadi. Asosiy himoya baribir backend'da. */
export function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.role)) return <NotFoundPage />
  return <Outlet />
}

/** Sahifa kodi yuklanmadi (tarmoq uzildi yoki yangi versiya chiqdi) yoki sahifada kutilmagan xato. */
export function RouteError() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-4 text-center" role="alert">
      <p className="text-sm text-muted-foreground">Sahifani ochib bo'lmadi. Internet aloqasini tekshirib, sahifani yangilang.</p>
      <Button variant="outline" onClick={() => window.location.reload()}>
        Yangilash
      </Button>
    </div>
  )
}

export function LoginRoute() {
  const { loading } = useAuth()
  if (loading) return <FullPageLoader />
  return <LoginPage />
}
