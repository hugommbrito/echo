import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TodayPage } from './TodayPage'

const profile = (code: string, target: number, active = true) => ({
  code,
  name: code === 'en' ? 'Inglês' : 'Francês (Canadá/Québec)',
  is_active: active,
  default_new_cards_per_day: target,
  activated_at: '2026-09-01T12:00:00Z',
  level: {
    rating: code === 'en' ? 1168 : 900,
    band: code === 'en' ? 'A2' : 'A1',
    provisional: true,
    counted_attempts: 4,
    initial_rating: code === 'en' ? 1150 : 900,
  },
})

const baseMe = {
  id: 'u1',
  email: 'ana@example.com',
  full_name: 'Ana',
  timezone: 'America/Sao_Paulo',
  feedback_language: 'pt-BR',
  is_staff: false,
  languages: [profile('en', 3), profile('fr', 2)],
}

const categories = [
  {
    id: 'c1',
    slug: 'travel',
    name: 'Travel',
    description: '',
    generation_hint: '',
    is_active: true,
    sort_order: 1,
    scope: 'global',
    card_count: 2,
  },
]

const projection = {
  languages: [
    {
      language: 'en',
      base_level: 'A2',
      carried_over: 0,
      available_carry_over: 0,
      to_generate: 3,
      probes: 1,
      due_today: 4,
      overdue: 1,
      total: 7,
    },
    {
      language: 'fr',
      base_level: 'A1',
      carried_over: 0,
      available_carry_over: 0,
      to_generate: 2,
      probes: 0,
      due_today: 0,
      overdue: 0,
      total: 2,
    },
  ],
  carried_over: 0,
  to_generate: 5,
  due_today: 4,
  overdue: 1,
  probes: 1,
  total: 9,
}

const calls: { url: string; body: unknown }[] = []

function stubFetch(me: typeof baseMe) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      const path = url.pathname.replace('/api/v1', '')
      calls.push({ url: url.pathname + url.search, body: init?.body ? JSON.parse(String(init.body)) : null })
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
      if (path === '/me/') return json(me)
      if (path === '/categories/') return json(categories)
      if (path === '/sessions/today/') return json({ detail: 'No session', code: 'no_session_today' }, 404)
      if (path === '/sessions/projection/') return json(projection)
      if (path === '/sessions/' && init?.method === 'POST')
        return json({ id: 's1', status: 'ready', plans: [], progress: {}, categories: [] }, 201)
      return json({ detail: 'nope', code: 'not_found' }, 404)
    }),
  )
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/today']}>
        <TodayPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TodayPage', () => {
  beforeEach(() => {
    calls.length = 0
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows one stepper per active language, prefilled with each default', async () => {
    stubFetch(baseMe)
    renderPage()
    const en = await screen.findByLabelText('Perguntas novas em inglês')
    const fr = screen.getByLabelText('Perguntas novas em francês')
    expect(en).toHaveValue(3)
    expect(fr).toHaveValue(2)
    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.url.includes('/sessions/projection/') && c.url.includes('targets=en%3A3%2Cfr%3A2'),
        ),
      ).toBe(true),
    )
    await waitFor(() => expect(screen.getByText(/9/)).toBeInTheDocument())
    expect(screen.getByText('Perguntas novas por idioma')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Começar/ }))
    await waitFor(() => expect(calls.some((c) => c.url === '/api/v1/sessions/' && c.body)).toBe(true))
    const post = calls.find((c) => c.url === '/api/v1/sessions/' && c.body)!
    expect(post.body).toMatchObject({ category_ids: ['c1'], new_cards_targets: { en: 3, fr: 2 } })
  })

  it('points to Settings when no language is active', async () => {
    stubFetch({ ...baseMe, languages: [profile('en', 3, false)] })
    renderPage()
    expect(await screen.findByText('Nenhum idioma ativo')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ativar idioma/ })).toHaveAttribute(
      'href',
      '/settings?tab=languages',
    )
    expect(calls.some((c) => c.url.includes('/sessions/projection/'))).toBe(false)
  })
})
