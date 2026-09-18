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

export function useUpdateMe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (patch: UserPatch) => api.patch<User>('/me/', patch),
    onSuccess: (user) => {
      queryClient.setQueryData(authKeys.me, user)
    },
  })
}
