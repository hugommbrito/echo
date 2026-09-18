import type { CefrBand, Probe } from '@/types/api'

export const CEFR_BANDS: readonly CefrBand[] = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'] as const

/** Rating thresholds from the plan (4.7.1). Mirrors the backend; display only. */
export function bandForRating(rating: number): CefrBand {
  if (rating < 1000) return 'A1'
  if (rating < 1200) return 'A2'
  if (rating < 1400) return 'B1'
  if (rating < 1600) return 'B2'
  if (rating < 1800) return 'C1'
  return 'C2'
}

/** "sonda ↑" / "sonda ↓" / null */
export function probeLabel(probe: Probe | null | undefined): string | null {
  if (probe === 'above') return 'sonda ↑'
  if (probe === 'below') return 'sonda ↓'
  return null
}

/** "B1 · sonda ↑" or just "B1". */
export function levelLabel(band: CefrBand | string, probe?: Probe | null): string {
  const probeText = probeLabel(probe)
  return probeText ? `${band} · ${probeText}` : band
}

export function probeDescription(probe: Probe): string {
  switch (probe) {
    case 'above':
      return 'Pergunta de sondagem um nível acima do seu.'
    case 'below':
      return 'Pergunta de sondagem um nível abaixo do seu.'
    default:
      return 'Pergunta no seu nível atual.'
  }
}

/** Was a probe answered "well"? actual ≥ 0,5 ⇔ composite ≥ 3 (at the level of the question). */
export function probePassed(actual: string | number): boolean {
  const n = typeof actual === 'string' ? Number(actual) : actual
  return Number.isFinite(n) && n >= 0.5
}
