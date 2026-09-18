import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useLogin, useMe } from '@/api/auth'
import { isApiError } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

function loginErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 401 || error.code === 'invalid_credentials') return 'E-mail ou senha inválidos.'
    if (error.status === 400)
      return (
        error.fieldError('email') ?? error.fieldError('password') ?? 'Verifique os campos e tente de novo.'
      )
    if (error.status >= 500) return 'O servidor está indisponível. Tente de novo em instantes.'
    return error.detail
  }
  return 'Não foi possível entrar. Verifique sua conexão.'
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/today'
  const me = useMe()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  if (me.data) return <Navigate to={from} replace />

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    login.mutate({ email: email.trim(), password }, { onSuccess: () => navigate(from, { replace: true }) })
  }

  return (
    <main className="flex min-h-dvh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <span
            aria-hidden="true"
            className="mb-2 grid size-12 place-items-center rounded-2xl bg-primary text-primary-fg"
          >
            <span className="size-3 rounded-full bg-primary-fg" />
          </span>
          <CardTitle className="text-display text-3xl">Echo</CardTitle>
          <CardDescription>Pratique inglês falado todos os dias.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="email">E-mail</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                inputMode="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={login.isError || undefined}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Senha</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={login.isError || undefined}
              />
            </div>
            {login.isError ? (
              <Alert variant="destructive">
                <AlertDescription>{loginErrorMessage(login.error)}</AlertDescription>
              </Alert>
            ) : null}
            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={login.isPending}
              disabled={!email || !password}
            >
              Entrar
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
