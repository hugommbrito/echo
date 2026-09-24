import type { Maturity } from '@/types/api'

export type Axis = 'structure' | 'grammar' | 'fluency'

export const AXES: readonly Axis[] = ['structure', 'grammar', 'fluency'] as const

export interface ColorToken {
  /** CSS custom property name, e.g. `--axis-structure`. */
  variable: `--${string}`
  /** Ready-to-use CSS value, e.g. `var(--axis-structure)`. */
  css: string
  /** Human label in pt-BR. */
  label: string
  /** Tailwind utility classes built on the token. */
  text: string
  bg: string
  border: string
}

export function token(variable: `--${string}`, label: string, tw: string): ColorToken {
  return {
    variable,
    css: `var(${variable})`,
    label,
    text: `text-${tw}`,
    bg: `bg-${tw}`,
    border: `border-${tw}`,
  }
}

/** Fixed colors for the three evaluation axes. Never reassign them. */
export const AXIS_COLORS: Record<Axis, ColorToken> = {
  structure: token('--axis-structure', 'Estrutura', 'axis-structure'),
  grammar: token('--axis-grammar', 'Gramática', 'axis-grammar'),
  fluency: token('--axis-fluency', 'Fluência', 'axis-fluency'),
}

/** Colors for the SM-2 maturity of a card. */
export const MATURITY_COLORS: Record<Maturity, ColorToken> = {
  new: token('--maturity-new', 'Novo', 'maturity-new'),
  learning: token('--maturity-learning', 'Aprendendo', 'maturity-learning'),
  mature: token('--maturity-mature', 'Maduro', 'maturity-mature'),
}

export const LEVEL_ACCENT = token('--level-accent', 'Nível', 'level-accent')

export const AXIS_LABELS: Record<Axis, string> = {
  structure: AXIS_COLORS.structure.label,
  grammar: AXIS_COLORS.grammar.label,
  fluency: AXIS_COLORS.fluency.label,
}

export const MATURITY_LABELS: Record<Maturity, string> = {
  new: MATURITY_COLORS.new.label,
  learning: MATURITY_COLORS.learning.label,
  mature: MATURITY_COLORS.mature.label,
}
