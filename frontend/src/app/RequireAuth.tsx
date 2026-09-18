import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useMe } from '@/api/auth'
import { isApiError } from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

/** Gate: loads `/me/`; 401/403 → `/login` (remembering where the user was). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation()
  const me = useMe()

  if (me.isPending) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner size="lg" label="Verificando sessão…" />
      </div>
    )
  }

  if (me.isError) {
    if (isApiError(me.error) && (me.error.status === 403 || me.error.status === 401)) {
      return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
    }
    return (
      <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 p-6">
        <Alert variant="destructive">
          <AlertTitle>Não foi possível carregar seu perfil</AlertTitle>
          <AlertDescription>
            {me.error instanceof Error ? me.error.message : 'Erro desconhecido.'}
          </AlertDescription>
        </Alert>
        <Button onClick={() => void me.refetch()}>Tentar de novo</Button>
      </div>
    )
  }

  return <>{children}</>
}
