import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Paginated, Projection, QueueItem, Session, SessionCreate } from '@/types/api'

import { api, isApiError } from './client'

export interface ProjectionParams {
  new_cards_target: number
  category_ids: string[]
}

export const sessionKeys = {
  all: ['sessions'] as const,
  today: () => [...sessionKeys.all, 'today'] as const,
  detail: (id: string) => [...sessionKeys.all, 'detail', id] as const,
  queue: (id: string, limit: number) => [...sessionKeys.all, 'queue', id, limit] as const,
  projection: (params: ProjectionParams) =>
    [
      ...sessionKeys.all,
      'projection',
      params.new_cards_target,
      [...params.category_ids].sort().join(','),
    ] as const,
  list: (params: { from?: string; to?: string }) => [...sessionKeys.all, 'list', params] as const,
}

const ACTIVE_STATUSES = new Set(['generating'])

/** Today's session, or `null` when the backend answers 404 `no_session_today`. */
export function useTodaySession() {
  return useQuery({
    queryKey: sessionKeys.today(),
    queryFn: async (): Promise<Session | null> => {
      try {
        return await api.get<Session>('/sessions/today/')
      } catch (error) {
        if (isApiError(error) && error.status === 404 && error.code === 'no_session_today') return null
        throw error
      }
    },
    staleTime: 0,
  })
}

export function useProjection(params: ProjectionParams, enabled = true) {
  return useQuery({
    queryKey: sessionKeys.projection(params),
    queryFn: () =>
      api.get<Projection>('/sessions/projection/', {
        new_cards_target: params.new_cards_target,
        category_ids: params.category_ids,
      }),
    enabled,
    placeholderData: (previous) => previous,
  })
}

export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SessionCreate) => api.post<Session>('/sessions/', payload),
    onSuccess: (session) => {
      queryClient.setQueryData(sessionKeys.today(), session)
      queryClient.setQueryData(sessionKeys.detail(session.id), session)
    },
  })
}

/** Session detail; polls every 2 s while `generating`. */
export function useSession(id: string | undefined) {
  return useQuery({
    queryKey: sessionKeys.detail(id ?? ''),
    queryFn: () => api.get<Session>(`/sessions/${id}/`),
    enabled: Boolean(id),
    staleTime: 0,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && ACTIVE_STATUSES.has(status) ? 2000 : false
    },
  })
}

export function useSessionQueue(id: string | undefined, limit = 1, enabled = true) {
  return useQuery({
    queryKey: sessionKeys.queue(id ?? '', limit),
    queryFn: () => api.get<QueueItem[]>(`/sessions/${id}/queue/`, { limit }),
    enabled: Boolean(id) && enabled,
    staleTime: 0,
  })
}

export function useRetryGeneration() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<Session>(`/sessions/${id}/retry-generation/`),
    onSuccess: (session) => {
      queryClient.setQueryData(sessionKeys.detail(session.id), session)
      queryClient.setQueryData(sessionKeys.today(), session)
    },
  })
}

export function useCompleteSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<Session>(`/sessions/${id}/complete/`),
    onSuccess: (session) => {
      queryClient.setQueryData(sessionKeys.detail(session.id), session)
      queryClient.setQueryData(sessionKeys.today(), session)
    },
  })
}

export function useSessions(params: { from?: string; to?: string } = {}) {
  return useQuery({
    queryKey: sessionKeys.list(params),
    queryFn: () => api.get<Paginated<Session>>('/sessions/', params),
  })
}
