import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Fragment, StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { Toaster } from '@/components/ui/sonner'
import { ApiError } from '@/lib/api'
import { AuthProvider } from '@/lib/auth'
import { initLang, useLang } from '@/lib/i18n'
import { router } from '@/router'

import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Ruxsat yoki "topilmadi" xatolarida qayta urinish foydasiz
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failureCount < 2,
    },
  },
})

/** Til almashganda butun interfeys qayta chiziladi; serverdan kelgan matnlar ham yangi tilda qayta olinadi. */
// eslint-disable-next-line react/only-export-components
function LocalizedApp() {
  const lang = useLang()
  useEffect(() => {
    void queryClient.invalidateQueries()
  }, [lang])
  return (
    <Fragment key={lang}>
      <RouterProvider router={router} />
      <Toaster position="top-center" richColors />
    </Fragment>
  )
}

void initLang().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <LocalizedApp />
        </AuthProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
})
