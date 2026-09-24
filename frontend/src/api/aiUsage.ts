import { useQuery } from '@tanstack/react-query'

import type { AIUsage } from '@/types/api'

import { api } from './client'

export const aiUsageKeys = {
  all: ['me', 'ai-usage'] as const,
}

/** The learner's own estimated AI spend (this month, all time, by key origin). */
export function useAIUsage(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: aiUsageKeys.all,
    queryFn: () => api.get<AIUsage>('/me/ai-usage/'),
    enabled: options.enabled ?? true,
    staleTime: 60_000,
  })
}
