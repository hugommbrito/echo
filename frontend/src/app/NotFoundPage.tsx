import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-4 py-24 text-center">
      <p className="text-display text-7xl text-fg-muted">404</p>
      <h1 className="text-xl font-semibold">Página não encontrada</h1>
      <p className="text-fg-muted">O endereço que você abriu não existe.</p>
      <Button asChild>
        <Link to="/today">Voltar para Hoje</Link>
      </Button>
    </div>
  )
}
