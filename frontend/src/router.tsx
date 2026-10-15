import { Loader2 } from 'lucide-react'
import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { useAuth } from '@/lib/auth'
import type { Role } from '@/lib/types'
import { GroupsPage } from '@/pages/admin/GroupsPage'
import { UsersPage } from '@/pages/admin/UsersPage'
import { AssignmentDetailPage } from '@/pages/AssignmentDetailPage'
import { AssignmentsPage } from '@/pages/AssignmentsPage'
import { HomePage } from '@/pages/HomePage'
import { LabDetailPage } from '@/pages/LabDetailPage'
import { LabsPage } from '@/pages/LabsPage'
import { LoginPage } from '@/pages/LoginPage'
import { QuizDetailPage } from '@/pages/QuizDetailPage'
import { QuizzesPage } from '@/pages/QuizzesPage'
import { MaterialsPage } from '@/pages/MaterialsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { SubmissionPage } from '@/pages/SubmissionPage'

function FullPageLoader() {
  return (
    <div className="flex min-h-svh items-center justify-center" role="status" aria-label="Yuklanmoqda">
      <Loader2 className="size-6 animate-spin text-muted-foreground" />
    </div>
  )
}

/** Sessiya tekshirilguncha kutadi; kirmagan foydalanuvchini login sahifasiga yuboradi. */
function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <FullPageLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <AppShell />
}

/** Sahifani faqat ko'rsatilgan rollarga ochadi. Asosiy himoya baribir backend'da. */
// eslint-disable-next-line react/only-export-components
export function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.role)) return <NotFoundPage />
  return <Outlet />
}

function LoginRoute() {
  const { loading } = useAuth()
  if (loading) return <FullPageLoader />
  return <LoginPage />
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginRoute /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/profile', element: <ProfilePage /> },
      { path: '/materials', element: <MaterialsPage /> },
      { path: '/assignments', element: <AssignmentsPage /> },
      { path: '/assignments/:id', element: <AssignmentDetailPage /> },
      { path: '/labs', element: <LabsPage /> },
      { path: '/labs/:id', element: <LabDetailPage /> },
      { path: '/quizzes', element: <QuizzesPage /> },
      { path: '/quizzes/:id', element: <QuizDetailPage /> },
      {
        element: <RequireRole roles={['admin']} />,
        children: [
          { path: '/users', element: <UsersPage /> },
          { path: '/groups', element: <GroupsPage /> },
        ],
      },
      {
        element: <RequireRole roles={['admin', 'teacher']} />,
        children: [{ path: '/submissions/:id', element: <SubmissionPage /> }],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
