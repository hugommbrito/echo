import { lazy, Suspense } from 'react'

// The dashboard pulls in Recharts; load it only when /stats is visited.
const StatsPage = lazy(() => import('./StatsPage').then((m) => ({ default: m.StatsPage })))

export function LazyStatsPage() {
  return (
    <Suspense fallback={<p className="p-6 text-fg-muted">Carregando estatísticas…</p>}>
      <StatsPage />
    </Suspense>
  )
}
