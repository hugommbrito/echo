import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { LoginPayload, User, UserPatch } from '@/types/api'

import { api, resetCsrfToken } from './client'

export const authKeys = {
  me: ['me'] as const,
}

export function fetchMe(): Promise<User> {
  return api.get<User>('/me/')
}

export function useMe(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: fetchMe,
    enabled: options.enabled ?? true,
    retry: false,
    staleTime: 5 * 60_000,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: LoginPayload) => api.post<User>('/auth/login/', payload),
    onSuccess: (user) => {
      queryClient.setQueryData(authKeys.me, user)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<undefined>('/auth/logout/'),
    onSettled: () => {
      resetCsrfToken()
      queryClient.clear()
    },
  })
}

/** PATCH /me/ with an optimistic update, so quick toggles (e.g. the question mode in the session
 * header) apply instantly; the server body is authoritative once it arrives. */
export function useUpdateMe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (patch: UserPatch) => api.patch<User>('/me/', patch),
    onMutate: async (patch) => {
      await queryClient.cancelQueries({ queryKey: authKeys.me })
      const previous = queryClient.getQueryData<User>(authKeys.me)
      if (previous) queryClient.setQueryData<User>(authKeys.me, { ...previous, ...patch })
      return { previous }
    },
    onError: (_error, _patch, context) => {
      if (context?.previous) queryClient.setQueryData(authKeys.me, context.previous)
    },
    onSuccess: (user) => {
      queryClient.setQueryData(authKeys.me, user)
    },
  })
}
