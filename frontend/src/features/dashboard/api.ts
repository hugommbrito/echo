import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { api } from '@/api/client'
import type {
  ActivityBucket,
  Advanced,
  CategoryOption,
  CategoryRow,
  Collection,
  Forecast,
  GrammarIssues,
  HeatmapCell,
  LevelStats,
  Overview,
  ScoreBucket,
} from './types'

export type StatsFilters = { from: string; to: string; category: string | null; language: string | null }

function getJson<T>(
  path: string,
  params: Record<string, string | number | null | undefined> = {},
): Promise<T> {
  return api.get<T>(`${path}`, params)
}

function periodParams(filters: StatsFilters) {
  return { from: filters.from, to: filters.to, category: filters.category, language: filters.language }
}

const common = { placeholderData: keepPreviousData, staleTime: 30_000 } as const

export function useOverview(filters: StatsFilters) {
  return useQuery({
    queryKey: ['stats', 'overview', filters],
    queryFn: () => getJson<Overview>('/stats/overview/', periodParams(filters)),
    ...common,
  })
}

export function useScores(filters: StatsFilters, bucket: 'day' | 'week') {
  return useQuery({
    queryKey: ['stats', 'scores', filters, bucket],
    queryFn: () => getJson<ScoreBucket[]>('/stats/scores/', { ...periodParams(filters), bucket }),
    ...common,
  })
}

export function useLevel(filters: StatsFilters) {
  return useQuery({
    queryKey: ['stats', 'level', filters.from, filters.to, filters.language],
    queryFn: () =>
      getJson<LevelStats>('/stats/level/', {
        from: filters.from,
        to: filters.to,
        language: filters.language,
      }),
    ...common,
  })
}

export function useActivity(filters: StatsFilters, bucket: 'day' | 'week') {
  return useQuery({
    queryKey: ['stats', 'activity', filters, bucket],
    queryFn: () => getJson<ActivityBucket[]>('/stats/activity/', { ...periodParams(filters), bucket }),
    ...common,
  })
}

export function useForecast(days: number, language: string | null) {
  return useQuery({
    queryKey: ['stats', 'forecast', days, language],
    queryFn: () => getJson<Forecast>('/stats/forecast/', { days, language }),
    ...common,
  })
}

export function useCollection(language: string | null) {
  return useQuery({
    queryKey: ['stats', 'collection', language],
    queryFn: () => getJson<Collection>('/stats/collection/', { language }),
    ...common,
  })
}

export function useGrammarIssues(filters: StatsFilters) {
  return useQuery({
    queryKey: ['stats', 'grammar-issues', filters],
    queryFn: () => getJson<GrammarIssues>('/stats/grammar-issues/', periodParams(filters)),
    ...common,
  })
}

export function useCategoryStats(filters: StatsFilters) {
  return useQuery({
    queryKey: ['stats', 'categories', filters.from, filters.to, filters.language],
    queryFn: () =>
      getJson<CategoryRow[]>('/stats/categories/', {
        from: filters.from,
        to: filters.to,
        language: filters.language,
      }),
    ...common,
  })
}

export function useHeatmap(year: number, category: string | null, language: string | null) {
  return useQuery({
    queryKey: ['stats', 'heatmap', year, category, language],
    queryFn: () => getJson<HeatmapCell[]>('/stats/heatmap/', { year, category, language }),
    ...common,
  })
}

export function useAdvanced(enabled: boolean, filters: StatsFilters) {
  return useQuery({
    queryKey: ['stats', 'advanced', filters],
    queryFn: () => getJson<Advanced>('/stats/advanced/', periodParams(filters)),
    enabled,
    ...common,
  })
}

export function useCategoryOptions() {
  return useQuery({
    queryKey: ['categories', 'active'],
    queryFn: () => getJson<CategoryOption[]>('/categories/', { active: 'true' }),
    staleTime: 5 * 60_000,
  })
}
