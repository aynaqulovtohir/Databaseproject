import type { ComponentType } from 'react'
import { createBrowserRouter } from 'react-router-dom'

import { FullPageLoader, LoginRoute, RequireAuth, RequireRole, RouteError } from '@/components/layout/RouteGuards'
import { NotFoundPage } from '@/pages/NotFoundPage'

/**
 * Sahifa kodi alohida bo'lakda: faqat shu sahifa birinchi marta ochilganda yuklanadi.
 * Login va 404 sahifalari bundan mustasno — ular darhol kerak bo'ladi.
 */
function page<K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) {
  return async () => {
    try {
      const module = await load()
      sessionStorage.removeItem(RELOADED_KEY)
      return { Component: module[name] }
    } catch (error) {
      // Yangi versiya chiqqach eski oynadagi bo'lak nomlari endi yo'q: bir marta yangilab ko'ramiz
      if (!sessionStorage.getItem(RELOADED_KEY)) {
        sessionStorage.setItem(RELOADED_KEY, '1')
        window.location.reload()
        return new Promise<never>(() => {})
      }
      throw error
    }
  }
}

const RELOADED_KEY = 'chunk-reload'

export const router = createBrowserRouter([
  {
    // Sahifa birinchi ochilganda uning kodi yuklanguncha
    HydrateFallback: FullPageLoader,
    ErrorBoundary: RouteError,
    children: [
      { path: '/login', element: <LoginRoute /> },
      // Ekspert baholashi: login yo'q, shaxsiy havola tokeni bilan
      { path: '/expert/:token', lazy: page(() => import('@/pages/ExpertPage'), 'ExpertPage') },
      {
        element: <RequireAuth />,
        children: [
          { path: '/', lazy: page(() => import('@/pages/HomePage'), 'HomePage') },
          { path: '/profile', lazy: page(() => import('@/pages/ProfilePage'), 'ProfilePage') },
          { path: '/materials', lazy: page(() => import('@/pages/MaterialsPage'), 'MaterialsPage') },
          { path: '/assignments', lazy: page(() => import('@/pages/AssignmentsPage'), 'AssignmentsPage') },
          { path: '/assignments/:id', lazy: page(() => import('@/pages/AssignmentDetailPage'), 'AssignmentDetailPage') },
          { path: '/labs', lazy: page(() => import('@/pages/LabsPage'), 'LabsPage') },
          { path: '/labs/:id', lazy: page(() => import('@/pages/LabDetailPage'), 'LabDetailPage') },
          { path: '/quizzes', lazy: page(() => import('@/pages/QuizzesPage'), 'QuizzesPage') },
          { path: '/quizzes/:id', lazy: page(() => import('@/pages/QuizDetailPage'), 'QuizDetailPage') },
          {
            element: <RequireRole roles={['admin', 'teacher']} />,
            children: [
              { path: '/statistics', lazy: page(() => import('@/pages/StatisticsPage'), 'StatisticsPage') },
              { path: '/competence', lazy: page(() => import('@/pages/CompetencePage'), 'CompetencePage') },
              { path: '/risk', lazy: page(() => import('@/pages/RiskPage'), 'RiskPage') },
              { path: '/ai-quality', lazy: page(() => import('@/pages/AIQualityPage'), 'AIQualityPage') },
              { path: '/blind-review', lazy: page(() => import('@/pages/BlindReviewPage'), 'BlindReviewPage') },
            ],
          },
          {
            element: <RequireRole roles={['admin']} />,
            children: [
              { path: '/users', lazy: page(() => import('@/pages/admin/UsersPage'), 'UsersPage') },
              { path: '/groups', lazy: page(() => import('@/pages/admin/GroupsPage'), 'GroupsPage') },
              { path: '/ai-usage', lazy: page(() => import('@/pages/admin/AIUsagePage'), 'AIUsagePage') },
            ],
          },
          {
            element: <RequireRole roles={['admin', 'teacher']} />,
            children: [{ path: '/submissions/:id', lazy: page(() => import('@/pages/SubmissionPage'), 'SubmissionPage') }],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
])
