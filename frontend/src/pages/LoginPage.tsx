import { Database, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'

import { AppearanceMenu } from '@/components/AppearanceMenu'
import { FormField } from '@/components/FormField'
import { LanguageMenu } from '@/components/LanguageMenu'
import { PasswordInput } from '@/components/PasswordInput'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { errorMessage } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { t } from '@/lib/i18n'

export function LoginPage() {
  const { user, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username.trim(), password)
    } catch (caught) {
      setError(errorMessage(caught))
      setSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-svh items-center justify-center bg-page p-4">
      <div className="absolute top-3 right-3 flex items-center gap-1">
        <LanguageMenu />
        <AppearanceMenu />
      </div>
      {/* NiceAdmin "pages-login": logo karta ustida, karta ichida markazlashgan sarlavha */}
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2">
          <div className="brand-gradient flex size-9 items-center justify-center rounded-md text-white">
            <Database className="size-5" aria-hidden="true" />
          </div>
          <span className="font-heading text-[1.625rem] leading-none font-bold text-heading">{t('MB loyihalash')}</span>
        </div>

        <Card>
          <CardHeader className="pt-2 text-center">
            <h1 className="font-heading text-2xl font-bold text-heading">{t('Tizimga kirish')}</h1>
            <CardDescription>{t('Login va parolni kiriting. Ularni administratordan olasiz.')}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="grid gap-4" noValidate>
              {error ? (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
              <FormField id="username" label={t('Login')}>
                <Input
                  id="username"
                  name="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  autoFocus
                  required
                  className="h-10"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </FormField>
              <FormField id="password" label={t('Parol')}>
                <PasswordInput
                  id="password"
                  name="password"
                  autoComplete="current-password"
                  required
                  className="h-10"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </FormField>
              <Button type="submit" className="h-10 w-full" disabled={submitting || !username.trim() || !password}>
                {submitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                {t('Kirish@@tizimga')}
              </Button>
            </form>
          </CardContent>
        </Card>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          {t("Ma'lumotlar bazasini loyihalash ta'lim platformasi")} · {t('Dizayn:')}{' '}
          <a href="https://bootstrapmade.com/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
            {t('BootstrapMade')}
          </a>
        </p>
      </div>
    </div>
  )
}
