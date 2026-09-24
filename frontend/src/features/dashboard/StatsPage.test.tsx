import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { StatsPage } from './StatsPage'

const level = (language: string, rating: number, band: string, initial: number, next: unknown) => ({
  language,
  rating,
  band,
  delta_period: rating - initial,
  provisional: true,
  counted_attempts: 9,
  initial_rating: initial,
  is_active: true,
  next_band: next,
})

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
  levels: [
    level('en', 1240, 'B1', 1150, { label: 'B2', points_needed: 160 }),
    level('fr', 980, 'A1', 900, { label: 'A2', points_needed: 20 }),
  ],
}

const me = {
  id: 'u1',
  email: 'ana@example.com',
  full_name: 'Ana',
  timezone: 'America/Sao_Paulo',
  feedback_language: 'pt-BR',
  is_staff: false,
  languages: [
    {
      code: 'en',
      name: 'Inglês',
      is_active: true,
      default_new_cards_per_day: 3,
      activated_at: '2026-09-01T12:00:00Z',
      level: { rating: 1240, band: 'B1', provisional: true, counted_attempts: 9, initial_rating: 1150 },
    },
    {
      code: 'fr',
      name: 'Francês (Canadá/Québec)',
      is_active: true,
      default_new_cards_per_day: 2,
      activated_at: '2026-09-20T12:00:00Z',
      level: { rating: 980, band: 'A1', provisional: true, counted_attempts: 1, initial_rating: 900 },
    },
  ],
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
  '/me/': me,
  '/languages/': [
    { code: 'en', name: 'Inglês', name_en: 'English', starting_levels: ['A1', 'A2', 'B1'] },
    { code: 'fr', name: 'Francês (Canadá/Québec)', name_en: 'French', starting_levels: ['A1', 'A2', 'B1'] },
  ],
  '/stats/level/': {
    period: overview.period,
    bands: [
      { label: 'A1', min: 0, max: 999, center: 900 },
      { label: 'A2', min: 1000, max: 1199, center: 1100 },
      { label: 'B1', min: 1200, max: 1399, center: 1300 },
    ],
    series: [
      {
        language: 'en',
        points: [
          { date: '2026-08-18', rating_after: 1150 },
          { date: '2026-09-16', rating_after: 1240 },
        ],
        probes: {
          above: { answered: 3, hits: 2, avg_actual: 0.7, avg_delta: 12 },
          below: { answered: 1, hits: 1, avg_actual: 0.9, avg_delta: 3 },
        },
        events: [{ date: '2026-09-16', delta: 20, rating_after: 1240, probe: 'above', hit: true }],
        current: { rating: 1240, band: 'B1' },
        initial_rating: 1150,
        is_active: true,
      },
      {
        language: 'fr',
        points: [
          { date: '2026-08-18', rating_after: 900 },
          { date: '2026-09-15', rating_after: 980 },
        ],
        probes: {
          above: { answered: 0, hits: 0, avg_actual: null, avg_delta: null },
          below: { answered: 0, hits: 0, avg_actual: null, avg_delta: null },
        },
        events: [],
        current: { rating: 980, band: 'A1' },
        initial_rating: 900,
        is_active: true,
      },
    ],
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
      {
        language: 'en',
        levels: [
          { level: 'A2', count: 5 },
          { level: 'B1', count: 7 },
        ],
      },
      {
        language: 'fr',
        levels: [
          { level: 'A2', count: 1 },
          { level: 'B1', count: 0 },
        ],
      },
    ],
    by_language: [
      { language: 'en', total: 12, new: 4, learning: 6, mature: 2, suspended: 1 },
      { language: 'fr', total: 1, new: 0, learning: 1, mature: 0, suspended: 0 },
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
  '/stats/advanced/': {
    ease: [{ ease: '2.5', count: 3 }],
    intervals: [{ range: '1-7', count: 3 }],
    answer_duration: { avg_seconds: 60, min_seconds: 30, max_seconds: 90, attempts: 6 },
    thinking_time: {
      avg_seconds: 8,
      median_seconds: 7,
      attempts: 3,
      series: [
        { date: '2026-09-06', median_seconds: 5, attempts: 1 },
        { date: '2026-09-16', median_seconds: 12, attempts: 1 },
      ],
    },
  },
  '/categories/': [{ id: 'c1', slug: 'travel', name: 'Travel', scope: 'global' }],
}

const calls: string[] = []

function renderPage(initialPath = '/stats') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <StatsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('StatsPage', () => {
  beforeEach(() => {
    calls.length = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input), 'http://localhost')
        calls.push(url.pathname + url.search)
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
    renderPage()
    await waitFor(() => expect(screen.getByText('Evolução do nível')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText(/160 pts p\/ B2/)).toBeInTheDocument())
    expect(screen.getByText(/20 pts p\/ A2/)).toBeInTheDocument() // second language in the Nível tile
    expect(screen.getByText('Evolução das notas')).toBeInTheDocument()
    expect(screen.getByText('Próximas revisões')).toBeInTheDocument()
    expect(screen.getByText('Erros de gramática mais frequentes')).toBeInTheDocument()
    expect(screen.getAllByText(/sondas acima:/).length).toBe(2) // one footer row per language
    expect(screen.getAllByText('Ver tabela').length).toBeGreaterThanOrEqual(5)
    expect(screen.getByRole('radio', { name: /30 dias/ })).toHaveAttribute('aria-checked', 'true')
  })

  it('offers a language selector when more than one language is active', async () => {
    renderPage()
    const group = await screen.findByRole('radiogroup', { name: 'Idioma' })
    expect(group).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Todos/ })).toHaveAttribute('aria-checked', 'true')
    // both languages appear in the level chart legend
    await waitFor(() => expect(screen.getAllByText('Inglês').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Francês').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('radio', { name: /Francês/ }))
    await waitFor(() =>
      expect(calls.some((c) => c.includes('/stats/overview/') && c.includes('language=fr'))).toBe(true),
    )
    expect(calls.some((c) => c.includes('/stats/level/') && c.includes('language=fr'))).toBe(true)
    expect(calls.some((c) => c.includes('/stats/collection/') && c.includes('language=fr'))).toBe(true)
  })

  it('reads the language from the URL (deep link from the header badge)', async () => {
    renderPage('/stats?language=fr')
    await screen.findByRole('radiogroup', { name: 'Idioma' })
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Francês/ })).toHaveAttribute('aria-checked', 'true'),
    )
    await waitFor(() =>
      expect(calls.some((c) => c.includes('/stats/scores/') && c.includes('language=fr'))).toBe(true),
    )
  })

  it('shows the thinking-time block in the advanced section, filtered by the period', async () => {
    renderPage()
    await screen.findByText('Evolução do nível')
    fireEvent.click(screen.getByRole('button', { name: /Avançado/ }))
    expect(await screen.findByText('Tempo para começar')).toBeInTheDocument()
    expect(screen.getByText('7,0 s')).toBeInTheDocument()
    expect(screen.getByText('mediana por dia, no período')).toBeInTheDocument()
    expect(
      calls.some((c) => c.includes('/stats/advanced/') && c.includes('from=') && c.includes('to=')),
    ).toBe(true)
  })
})
