import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type {
  LanguageCatalogItem,
  LanguageProfile,
  LanguageProfileCreate,
  LanguageProfilePatch,
} from '@/types/api'

import { authKeys } from './auth'
import { api } from './client'
import { sessionKeys } from './sessions'

export const languageKeys = {
  catalog: ['languages'] as const,
}

/** Languages the app supports, activated or not. */
export function useLanguageCatalog() {
  return useQuery({
    queryKey: languageKeys.catalog,
    queryFn: () => api.get<LanguageCatalogItem[]>('/languages/'),
    staleTime: 60 * 60_000,
  })
}

export function useActivateLanguage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: LanguageProfileCreate) => api.post<LanguageProfile>('/me/languages/', payload),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: authKeys.me })
      void queryClient.invalidateQueries({ queryKey: sessionKeys.today() })
    },
  })
}

export function useUpdateLanguageProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ code, patch }: { code: string; patch: LanguageProfilePatch }) =>
      api.patch<LanguageProfile>(`/me/languages/${code}/`, patch),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: authKeys.me })
      void queryClient.invalidateQueries({ queryKey: sessionKeys.all })
    },
  })
}
