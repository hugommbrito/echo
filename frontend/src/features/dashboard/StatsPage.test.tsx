import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { StatsPage } from './StatsPage'

const overview = {
  period: { from: '2026-08-18', to: '2026-09-16', days: 30 },
  today: {
    answered: 3,
    new_answered: 2,
    due_answered: 1,
    target: 3,
    session_id: 's1',
    session_status: 'in_progress',
  },
  due: { today: 2, overdue: 1, next_7_days: 5 },
  collection: { total: 12, new: 4, learning: 6, mature: 2, suspended: 1 },
  scores: {
    period: { structure_avg: 3.6, grammar_avg: 3.1, fluency_avg: 3.4, composite_avg: 3.4, attempts: 9 },
    previous_period: {
      structure_avg: 3.2,
      grammar_avg: 3.0,
      fluency_avg: 3.1,
      composite_avg: 3.1,
      attempts: 4,
    },
  },
  level: {
    rating: 1240,
    band: 'B1',
    delta_period: 35,
    provisional: true,
    counted_attempts: 9,
    initial_rating: 1150,
    next_band: { label: 'B2', points_needed: 160 },
  },
}

const responses: Record<string, unknown> = {
  '/stats/overview/': overview,
  '/stats/scores/': [
    {
      bucket_start: '2026-09-10',
      structure_avg: 3,
      grammar_avg: 3,
      fluency_avg: 3,
      composite_avg: 3,
      attempts: 2,
    },
    {
      bucket_start: '2026-09-16',
      structure_avg: 4,
      grammar_avg: 3,
      fluency_avg: 4,
      composite_avg: 3.65,
      attempts: 3,
    },
  ],
  '/stats/level/': {
    period: overview.period,
    points: [
      { date: '2026-08-18', rating_after: 1150 },
      { date: '2026-09-16', rating_after: 1240 },
    ],
    bands: [
      { label: 'A2', min: 1000, max: 1199, center: 1100 },
      { label: 'B1', min: 1200, max: 1399, center: 1300 },
    ],
    probes: {
      above: { answered: 3, hits: 2, avg_actual: 0.7, avg_delta: 12 },
      below: { answered: 1, hits: 1, avg_actual: 0.9, avg_delta: 3 },
    },
    events: [{ date: '2026-09-16', delta: 20, rating_after: 1240, probe: 'above', hit: true }],
    current: { rating: 1240, band: 'B1' },
    initial_rating: 1150,
  },
  '/stats/activity/': [
    { bucket_start: '2026-09-16', new: 2, learning: 1, mature: 0, total: 3, speaking_seconds: 180 },
  ],
  '/stats/forecast/': {
    days: [
      { date: '2026-09-16', due: 3 },
      { date: '2026-09-17', due: 1 },
    ],
    overdue: 1,
    total: 4,
  },
  '/stats/collection/': {
    by_maturity: { new: 4, learning: 6, mature: 2, suspended: 1 },
    by_category: [
      { category: { id: 'c1', slug: 'travel', name: 'Travel' }, new: 1, learning: 2, mature: 1, total: 4 },
    ],
    by_level: [
      { level: 'A2', count: 5 },
      { level: 'B1', count: 7 },
    ],
  },
  '/stats/grammar-issues/': {
    period: overview.period,
    items: [
      {
        type: 'verb_tense',
        count: 4,
        previous_count: 2,
        delta: 2,
        examples: [{ quote: 'I go', correction: 'I went' }],
      },
    ],
    total: 4,
    previous_total: 2,
  },
  '/stats/categories/': [
    {
      category: { id: 'c1', slug: 'travel', name: 'Travel', scope: 'global' },
      cards: 4,
      attempts: 5,
      structure_avg: 3.5,
      grammar_avg: 3.2,
      fluency_avg: 3.8,
      composite_avg: 3.5,
      trend: [
        { week_start: '2026-09-07', composite_avg: 3.2 },
        { week_start: '2026-09-14', composite_avg: 3.5 },
      ],
    },
  ],
  '/stats/heatmap/': [{ date: '2026-09-16', count: 3, speaking_seconds: 180 }],
  '/categories/': [{ id: 'c1', slug: 'travel', name: 'Travel', scope: 'global' }],
}

describe('StatsPage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input), 'http://localhost')
        const key = url.pathname.replace('/api/v1', '')
        const body = responses[key]
        if (body === undefined)
          return new Response(JSON.stringify({ detail: 'nope', code: 'not_found' }), { status: 404 })
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders tiles, charts and footers from the stats API', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <StatsPage />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(screen.getByText('Evolução do nível')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText(/160 pts p\/ B2/)).toBeInTheDocument())
    expect(screen.getByText('Evolução das notas')).toBeInTheDocument()
    expect(screen.getByText('Próximas revisões')).toBeInTheDocument()
    expect(screen.getByText('Erros de gramática mais frequentes')).toBeInTheDocument()
    expect(screen.getByText(/sondas acima:/)).toBeInTheDocument()
    expect(screen.getAllByText('Ver tabela').length).toBeGreaterThanOrEqual(5)
    expect(screen.getByRole('radio', { name: /30 dias/ })).toHaveAttribute('aria-checked', 'true')
  })
})
