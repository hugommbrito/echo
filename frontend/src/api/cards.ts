import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Attempt, Card, CardDetail, CardFilters, Paginated } from '@/types/api'

import { API_BASE, api } from './client'

export const cardKeys = {
  all: ['cards'] as const,
  list: (filters: CardFilters) => [...cardKeys.all, 'list', filters] as const,
  detail: (id: string) => [...cardKeys.all, 'detail', id] as const,
  history: (id: string) => [...cardKeys.all, 'history', id] as const,
}

export function useCards(filters: CardFilters) {
  return useQuery({
    queryKey: cardKeys.list(filters),
    queryFn: () =>
      api.get<Paginated<Card>>('/cards/', {
        language: filters.language,
        category: filters.category,
        maturity: filters.maturity,
        level: filters.level,
        status: filters.status,
        q: filters.q,
        page: filters.page,
        page_size: filters.page_size,
      }),
    placeholderData: (previous) => previous,
  })
}

export function useCard(id: string | undefined) {
  return useQuery({
    queryKey: cardKeys.detail(id ?? ''),
    queryFn: () => api.get<CardDetail>(`/cards/${id}/`),
    enabled: Boolean(id),
  })
}

export function useCardHistory(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: cardKeys.history(id ?? ''),
    queryFn: () => api.get<Attempt[]>(`/cards/${id}/history/`),
    enabled: Boolean(id) && enabled,
    staleTime: 0,
  })
}

function useCardStatusMutation(action: 'suspend' | 'unsuspend') {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<CardDetail>(`/cards/${id}/${action}/`),
    onSuccess: (card) => {
      queryClient.setQueryData(cardKeys.detail(card.id), card)
      void queryClient.invalidateQueries({ queryKey: [...cardKeys.all, 'list'] })
    },
  })
}

export function useSuspendCard() {
  return useCardStatusMutation('suspend')
}

export function useUnsuspendCard() {
  return useCardStatusMutation('unsuspend')
}

/** Always-fresh spoken question: synthesises on demand and 302s to the (signed) file. */
export function questionAudioFallbackSrc(cardId: string): string {
  return `${API_BASE}/cards/${cardId}/audio/`
}

/** Prefer the URL already in the payload; fall back to the on-demand endpoint. */
export function questionAudioSrc(card: Pick<Card, 'id' | 'question_audio_url'>): string {
  return card.question_audio_url ?? questionAudioFallbackSrc(card.id)
}
