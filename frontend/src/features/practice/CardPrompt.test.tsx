import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Card } from '@/types/api'

import { CardPrompt } from './CardPrompt'

const card: Card = {
  id: 'c1',
  language: 'en',
  category: { id: 'k1', slug: 'travel', name: 'Viagem', scope: 'global' },
  question_text: 'Tell me about your last trip.',
  scenario: 'You are chatting with a colleague in Toronto.',
  key_points: [],
  cefr_level: 'A2',
  difficulty_rating: 1100,
  probe: 'none',
  status: 'active',
  source: 'generated',
  maturity: 'new',
  attempt_count: 0,
  question_audio_url: null,
  question_audio_seconds: null,
  created_at: '2026-09-23T12:00:00Z',
}

describe('CardPrompt', () => {
  it('read mode shows the question text and no audio slot', () => {
    render(<CardPrompt card={card} audio={<div data-testid="audio" />} mode="read" />)
    expect(screen.getByRole('heading', { name: card.question_text })).toHaveAttribute('lang', 'en-CA')
    expect(screen.getByTestId('audio')).toBeInTheDocument() // the slot is the parent's call
    expect(screen.queryByRole('button', { name: 'Mostrar texto' })).toBeNull()
  })

  it('listen mode keeps the text out of the DOM until "Mostrar texto"', () => {
    const onReveal = vi.fn()
    render(
      <CardPrompt
        card={card}
        mode="listen"
        textRevealed={false}
        onRevealText={onReveal}
        audio={<div data-testid="audio" />}
      />,
    )
    expect(screen.queryByText(card.question_text)).toBeNull()
    expect(screen.getByText(card.scenario!)).toBeInTheDocument() // the scenario stays visible
    expect(screen.getByTestId('audio')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Mostrar texto' }))
    expect(onReveal).toHaveBeenCalledTimes(1)
  })

  it('shows the text once revealed, with the language tag', () => {
    render(<CardPrompt card={card} mode="listen" textRevealed />)
    expect(screen.getByRole('heading', { name: card.question_text })).toHaveAttribute('lang', 'en-CA')
    expect(screen.queryByRole('button', { name: 'Mostrar texto' })).toBeNull()
  })

  it('compact always shows the text and never the audio slot', () => {
    render(<CardPrompt card={card} mode="listen" compact audio={<div data-testid="audio" />} />)
    expect(screen.getByText(card.question_text)).toBeInTheDocument()
    expect(screen.queryByTestId('audio')).toBeNull()
  })
})
