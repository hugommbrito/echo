import { token, type ColorToken } from '@/lib/colors'
import { findProfile } from '@/lib/languages'
import type { ThinkingTimeProfile, User } from '@/types/api'

/**
 * Thinking time = seconds between the question being shown and the first press on "record",
 * compared with the learner's OWN reference (median of her recent attempts in that language).
 * Zones: green up to the reference, yellow up to 1.5×, red above. There is no lower bound:
 * answering faster is never penalised. Mirrors `apps/practice/thinking_time.py`.
 */
export type ThinkingZone = 'good' | 'ok' | 'slow'

export const OK_MULTIPLIER = 1.5

export const ZONE_LABELS: Record<ThinkingZone, string> = {
  good: 'no ritmo',
  ok: 'um pouco acima',
  slow: 'bem acima',
}

/** Status hues already defined in `index.css` (light + dark); colour never travels alone. */
export const ZONE_COLORS: Record<ThinkingZone, ColorToken> = {
  good: token('--success', 'No ritmo', 'success'),
  ok: token('--warning', 'Um pouco acima', 'warning'),
  slow: token('--danger', 'Bem acima', 'danger'),
}

/** `null` when there is no reference yet (neutral display). */
export function zoneFor(seconds: number, baseline: number | null | undefined): ThinkingZone | null {
  if (baseline == null || !Number.isFinite(baseline) || baseline <= 0) return null
  if (seconds <= baseline) return 'good'
  if (seconds <= baseline * OK_MULTIPLIER) return 'ok'
  return 'slow'
}

export function baselineFor(me: User | undefined | null, language: string): ThinkingTimeProfile | null {
  return findProfile(me, language)?.thinking_time ?? null
}

/** Boundary coercion: the API sends numbers, but legacy decimals arrive as strings. */
export function toSeconds(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'string' ? Number(value) : value
  return Number.isFinite(n) ? n : null
}
