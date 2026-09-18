import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Category, CategoryCreate, CategoryPatch } from '@/types/api'

import { api } from './client'

export interface CategoryListParams {
  active?: boolean
}

export const categoryKeys = {
  all: ['categories'] as const,
  list: (params: CategoryListParams = {}) => [...categoryKeys.all, 'list', params] as const,
}

export function useCategories(params: CategoryListParams = {}) {
  return useQuery({
    queryKey: categoryKeys.list(params),
    queryFn: () =>
      api.get<Category[]>('/categories/', {
        active: params.active === undefined ? undefined : params.active ? 'true' : 'false',
      }),
  })
}

export function useCreateCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CategoryCreate) => api.post<Category>('/categories/', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoryKeys.all }),
  })
}

export function useUpdateCategory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: CategoryPatch }) =>
      api.patch<Category>(`/categories/${id}/`, patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoryKeys.all }),
  })
}

/** Derive a URL-safe slug from a category name ("Viagem & Aeroporto" → "viagem-aeroporto"). */
export function slugify(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 50)
}
