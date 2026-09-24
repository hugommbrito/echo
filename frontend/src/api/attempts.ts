import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Attempt, AttemptAccepted, AttemptStatus, ImprovedAnswer, QuestionMode } from '@/types/api'

import { aiUsageKeys } from './aiUsage'
import { authKeys } from './auth'
import { cardKeys } from './cards'
import { api } from './client'
import { sessionKeys } from './sessions'

export const attemptKeys = {
  all: ['attempts'] as const,
  detail: (id: string) => [...attemptKeys.all, 'detail', id] as const,
}

export const TERMINAL_STATUSES: ReadonlySet<AttemptStatus> = new Set<AttemptStatus>(['completed', 'failed'])

export interface CreateAttemptInput {
  cardId: string
  sessionId?: string | null
  audio: Blob
  /** Client-side timer, seconds. */
  durationSeconds: number
  mimeType: string
  /** e.g. `webm`, `mp4`, `ogg` */
  extension: string
  /** Question shown → first press on record. `null`/omitted = not measured (immediate retake). */
  thinkingSeconds?: number | null
  /** How the question was presented when she pressed record. */
  questionMode?: QuestionMode | null
  /** Times the spoken question was played before recording. */
  audioReplays?: number
  /** In listen mode: she asked to see the text before recording. */
  textRevealed?: boolean
}

/** Upper bound accepted by the server's DecimalField (it clamps further to its own maximum). */
export const MAX_THINKING_SECONDS = 9999.99

export function buildAttemptFormData(input: CreateAttemptInput): FormData {
  const form = new FormData()
  form.append('card_id', input.cardId)
  if (input.sessionId) form.append('session_id', input.sessionId)
  form.append('audio', input.audio, `recording.${input.extension}`)
  form.append('duration_seconds', input.durationSeconds.toFixed(2))
  form.append('mime_type', input.mimeType)
  if (input.thinkingSeconds != null && Number.isFinite(input.thinkingSeconds)) {
    form.append(
      'thinking_seconds',
      Math.min(MAX_THINKING_SECONDS, Math.max(0, input.thinkingSeconds)).toFixed(2),
    )
  }
  if (input.questionMode) form.append('question_mode', input.questionMode)
  if (input.audioReplays != null)
    form.append('audio_replays', String(Math.max(0, Math.floor(input.audioReplays))))
  if (input.textRevealed != null) form.append('text_revealed', input.textRevealed ? 'true' : 'false')
  return form
}

export function useCreateAttempt() {
  return useMutation({
    mutationFn: (input: CreateAttemptInput) =>
      api.post<AttemptAccepted>('/attempts/', buildAttemptFormData(input)),
  })
}

/** Attempt detail; polls every 2 s until `completed` or `failed`. */
export function useAttempt(id: string | undefined) {
  return useQuery({
    queryKey: attemptKeys.detail(id ?? ''),
    queryFn: () => api.get<Attempt>(`/attempts/${id}/`),
    enabled: Boolean(id),
    staleTime: 0,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status) return 2000
      return TERMINAL_STATUSES.has(status) ? false : 2000
    },
  })
}

export function useRetryAttempt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<Attempt>(`/attempts/${id}/retry/`),
    onSuccess: (attempt) => {
      queryClient.setQueryData(attemptKeys.detail(attempt.id), attempt)
    },
  })
}

export function useImprovedAnswer(attemptId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<ImprovedAnswer>(`/attempts/${attemptId}/improved-answer/`),
    onSuccess: (result) => {
      queryClient.setQueryData<Attempt>(attemptKeys.detail(attemptId), (current) =>
        current?.evaluation
          ? {
              ...current,
              evaluation: {
                ...current.evaluation,
                improved_answer: result.improved_answer,
                improved_answer_notes: result.notes,
              },
            }
          : current,
      )
    },
  })
}

/** After an attempt finishes, everything derived from it may have changed. */
export function useInvalidateAfterAttempt() {
  const queryClient = useQueryClient()
  return (attempt: Attempt) => {
    void queryClient.invalidateQueries({ queryKey: cardKeys.history(attempt.card_id) })
    void queryClient.invalidateQueries({ queryKey: cardKeys.detail(attempt.card_id) })
    void queryClient.invalidateQueries({ queryKey: authKeys.me }) // level + thinking-time baseline
    void queryClient.invalidateQueries({ queryKey: aiUsageKeys.all })
    if (attempt.session_id) {
      void queryClient.invalidateQueries({ queryKey: sessionKeys.detail(attempt.session_id) })
      void queryClient.invalidateQueries({ queryKey: sessionKeys.today() })
    }
  }
}
