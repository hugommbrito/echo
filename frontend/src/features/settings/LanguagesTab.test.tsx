import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LanguagesTab } from './LanguagesTab'

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
      level: { rating: 1168, band: 'A2', provisional: true, counted_attempts: 4, initial_rating: 1150 },
    },
  ],
}

const catalog = [
  { code: 'en', name: 'Inglês', name_en: 'English', starting_levels: ['A1', 'A2', 'B1'] },
  {
    code: 'fr',
    name: 'Francês (Canadá/Québec)',
    name_en: 'French (Canada/Québec)',
    starting_levels: ['A1', 'A2', 'B1'],
  },
]

const calls: { url: string; method: string; body: unknown }[] = []

describe('LanguagesTab', () => {
  beforeEach(() => {
    calls.length = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), 'http://localhost')
        const path = url.pathname.replace('/api/v1', '')
        const method = init?.method ?? 'GET'
        calls.push({ url: path, method, body: init?.body ? JSON.parse(String(init.body)) : null })
        const json = (body: unknown, status = 200) =>
          new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
        if (path === '/me/') return json(me)
        if (path === '/languages/') return json(catalog)
        if (path === '/me/languages/' && method === 'POST')
          return json(
            {
              ...catalog[1],
              is_active: true,
              default_new_cards_per_day: 3,
              activated_at: '2026-09-23T12:00:00Z',
              level: { rating: 900, band: 'A1', provisional: true, counted_attempts: 0, initial_rating: 900 },
            },
            201,
          )
        if (path === '/me/languages/en/' && method === 'PATCH')
          return json({ ...me.languages[0], ...(init?.body ? JSON.parse(String(init.body)) : {}) })
        return json({ detail: 'nope', code: 'not_found' }, 404)
      }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  function renderTab() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
      <QueryClientProvider client={client}>
        <LanguagesTab />
      </QueryClientProvider>,
    )
  }

  it('lists activated and not-yet-activated languages and activates one at A1 by default', async () => {
    renderTab()
    expect(await screen.findByText('Não ativado')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Pausar inglês' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByLabelText('Perguntas novas por dia')).toHaveValue(3)

    fireEvent.click(screen.getByRole('button', { name: 'Ativar' }))
    const a1 = await screen.findByRole('radio', { name: /A1 — Iniciante/ })
    expect(a1).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Ativar idioma' }))
    await waitFor(() =>
      expect(calls.some((c) => c.url === '/me/languages/' && c.method === 'POST')).toBe(true),
    )
    const post = calls.find((c) => c.url === '/me/languages/' && c.method === 'POST')!
    expect(post.body).toEqual({ language: 'fr', starting_level: 'A1' })
  })

  it('pauses a language with the switch', async () => {
    renderTab()
    const toggle = await screen.findByRole('switch', { name: 'Pausar inglês' })
    fireEvent.click(toggle)
    await waitFor(() =>
      expect(calls.some((c) => c.url === '/me/languages/en/' && c.method === 'PATCH')).toBe(true),
    )
    const patch = calls.find((c) => c.url === '/me/languages/en/' && c.method === 'PATCH')!
    expect(patch.body).toEqual({ is_active: false })
  })
})
