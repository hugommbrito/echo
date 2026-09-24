import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AIUsageTab } from './AIUsageTab'

const baseMe = {
  id: 'u1',
  email: 'ana@example.com',
  full_name: 'Ana',
  timezone: 'America/Sao_Paulo',
  feedback_language: 'pt-BR',
  question_mode: 'read',
  show_thinking_timer: true,
  is_staff: false,
  languages: [],
}

const usage = {
  month: { starts_on: '2026-09-01', anthropic_usd: 0.1, openai_usd: 0.0234, total_usd: 0.1234, requests: 7 },
  all_time: { anthropic_usd: 1.5, openai_usd: 0.25, total_usd: 1.75, requests: 42 },
  by_key_source: { user_usd: 1.5, global_usd: 0.25 },
}

function stubFetch(ai: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname.replace('/api/v1', '')
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
      if (path === '/me/ai-usage/') return json(usage)
      if (path === '/me/') return json({ ...baseMe, ai })
      return json({ detail: 'nope', code: 'not_found' }, 404)
    }),
  )
}

function renderTab() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AIUsageTab />
    </QueryClientProvider>,
  )
}

describe('AIUsageTab', () => {
  beforeEach(() => {
    stubFetch({
      llm_provider: 'anthropic',
      speech_available: true,
      anthropic: { configured: true, hint: '…1234', source: 'user' },
      openai: { configured: false, hint: null, source: 'global' },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows where each provider is served from and the estimated costs, never a key', async () => {
    renderTab()
    expect(await screen.findByText('configurada · …1234')).toBeInTheDocument()
    expect(screen.getByText('usando a chave do Echo')).toBeInTheDocument()
    expect(
      screen.getByText(/Textos .*Anthropic \(sua chave\) · Fala .*OpenAI \(chave do Echo\)/),
    ).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Custo estimado por provedor' })
    expect(table).toHaveTextContent(/US\$\s0,10/)
    expect(table).toHaveTextContent(/US\$\s0,0234/)
    expect(table).toHaveTextContent(/US\$\s1,75/)
    expect(screen.getByText(/7 chamadas este mês, 42 no total/)).toBeInTheDocument()
    expect(screen.queryByText(/indisponíveis/)).toBeNull()
    expect(document.body.textContent).not.toMatch(/sk-/)
  })

  it('warns when speech is unavailable', async () => {
    vi.unstubAllGlobals()
    stubFetch({
      llm_provider: 'anthropic',
      speech_available: false,
      anthropic: { configured: true, hint: '…9999', source: 'user' },
      openai: { configured: false, hint: null, source: 'none' },
    })
    renderTab()
    expect(await screen.findByText(/Transcrição e áudio das perguntas indisponíveis/)).toBeInTheDocument()
    expect(screen.getByText('não disponível')).toBeInTheDocument()
  })
})
