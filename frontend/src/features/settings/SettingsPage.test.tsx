import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SettingsPage } from './SettingsPage'

const me = {
  id: 'u1',
  email: 'ana@example.com',
  full_name: 'Ana',
  timezone: 'America/Sao_Paulo',
  feedback_language: 'pt-BR',
  question_mode: 'read',
  show_thinking_timer: true,
  is_staff: false,
  languages: [
    {
      code: 'en',
      name: 'Inglês',
      is_active: true,
      default_new_cards_per_day: 3,
      activated_at: '2026-09-01T12:00:00Z',
      level: { rating: 1168, band: 'A2', provisional: true, counted_attempts: 4, initial_rating: 1150 },
      thinking_time: { baseline_seconds: 6, samples: 4, is_default: true },
    },
  ],
  ai: {
    llm_provider: 'anthropic',
    speech_available: true,
    anthropic: { configured: false, hint: null, source: 'global' },
    openai: { configured: false, hint: null, source: 'global' },
  },
}

const calls: { url: string; method: string; body: unknown }[] = []
let resolvePatch: ((value: Response) => void) | null = null

describe('SettingsPage › Preferências', () => {
  beforeEach(() => {
    calls.length = 0
    resolvePatch = null
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), 'http://localhost')
        const path = url.pathname.replace('/api/v1', '')
        const method = init?.method ?? 'GET'
        const body = init?.body ? JSON.parse(String(init.body)) : null
        calls.push({ url: path, method, body })
        const json = (payload: unknown, status = 200) =>
          new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
        if (path === '/me/' && method === 'PATCH') {
          return new Promise<Response>((resolve) => {
            resolvePatch = () => resolve(json({ ...me, ...body }))
          })
        }
        if (path === '/me/') return json(me)
        if (path === '/categories/') return json([])
        if (path === '/languages/') return json([])
        return json({ detail: 'nope', code: 'not_found' }, 404)
      }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  function renderPage() {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    return render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/settings']}>
          <SettingsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )
  }

  it('saves the question mode and the timer preference, applying them optimistically', async () => {
    renderPage()
    const group = await screen.findByRole('radiogroup', { name: 'Como ver a pergunta' })
    expect(within(group).getByRole('radio', { name: 'Ler' })).toHaveAttribute('aria-checked', 'true')
    const save = screen.getByRole('button', { name: 'Salvar' })
    expect(save).toBeDisabled()

    fireEvent.click(within(group).getByRole('radio', { name: 'Ouvir' }))
    expect(
      screen.getByText('Só o áudio; o texto fica escondido até você pedir.', { exact: false }),
    ).toBeInTheDocument()
    const timer = screen.getByRole('switch', { name: 'Mostrar cronômetro de tempo para começar' })
    expect(timer).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(timer)
    expect(save).toBeEnabled()
    fireEvent.click(save)

    await waitFor(() => expect(calls.some((c) => c.url === '/me/' && c.method === 'PATCH')).toBe(true))
    const patch = calls.find((c) => c.url === '/me/' && c.method === 'PATCH')!
    expect(patch.body).toEqual({
      timezone: 'America/Sao_Paulo',
      feedback_language: 'pt-BR',
      question_mode: 'listen',
      show_thinking_timer: false,
    })

    // optimistic: the cached profile already reflects the patch while the request is in flight
    await waitFor(() => {
      const regroup = screen.getByRole('radiogroup', { name: 'Como ver a pergunta' })
      expect(within(regroup).getByRole('radio', { name: 'Ouvir' })).toHaveAttribute('aria-checked', 'true')
    })
    expect(resolvePatch).not.toBeNull()
    resolvePatch!(new Response())
    await waitFor(() => expect(screen.getByText('Preferências salvas.')).toBeInTheDocument())
  })

  it('has an "IA e custos" tab', async () => {
    renderPage()
    expect(await screen.findByRole('tab', { name: 'IA e custos' })).toBeInTheDocument()
  })
})
