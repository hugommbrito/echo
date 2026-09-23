import type { LanguageCode, LanguageProfile, User } from '@/types/api'

/**
 * Frontend side of the language registry (backend: `apps/core/languages.py`).
 * Display names come from the API (`LanguageProfile.name`); this file holds what the UI needs
 * offline: short tags, pt-BR phrases, the `lang` attribute and the chart/token color.
 */
export interface LanguageMeta {
  code: string
  /** "Inglês" */
  label: string
  /** "EN" */
  short: string
  /** "em inglês" */
  inPhrase: string
  /** BCP-47 tag for `lang` attributes: Canadian varieties for both. */
  htmlLang: string
  /** CSS custom property with the language color (see docs/dataviz-palette.md → Idiomas). */
  colorVar: `--${string}`
}

export const LANGUAGE_ORDER: readonly LanguageCode[] = ['en', 'fr'] as const

export const LANGUAGES: Record<LanguageCode, LanguageMeta> = {
  en: {
    code: 'en',
    label: 'Inglês',
    short: 'EN',
    inPhrase: 'em inglês',
    htmlLang: 'en-CA',
    colorVar: '--language-en',
  },
  fr: {
    code: 'fr',
    label: 'Francês',
    short: 'FR',
    inPhrase: 'em francês',
    htmlLang: 'fr-CA',
    colorVar: '--language-fr',
  },
}

export function isLanguageCode(code: string | null | undefined): code is LanguageCode {
  return code != null && Object.hasOwn(LANGUAGES, code)
}

/** Meta for a code; unknown codes (a future third language) still render, in ink. */
export function languageMeta(code: string): LanguageMeta {
  if (isLanguageCode(code)) return LANGUAGES[code]
  const upper = code.toUpperCase()
  return {
    code,
    label: upper,
    short: upper,
    inPhrase: `em ${upper}`,
    htmlLang: code,
    colorVar: '--chart-ink',
  }
}

export function languageOrder(code: string): number {
  const index = (LANGUAGE_ORDER as readonly string[]).indexOf(code)
  return index === -1 ? LANGUAGE_ORDER.length : index
}

/** Stable order for badges, steppers, series and legends. */
export function sortByLanguage<T>(items: readonly T[], code: (item: T) => string): T[] {
  return [...items].sort((a, b) => languageOrder(code(a)) - languageOrder(code(b)))
}

export function activeLanguages(me: User | undefined | null): LanguageProfile[] {
  if (!me) return []
  return sortByLanguage(
    me.languages.filter((profile) => profile.is_active),
    (profile) => profile.code,
  )
}

export function findProfile(me: User | undefined | null, code: string): LanguageProfile | undefined {
  return me?.languages.find((profile) => profile.code === code)
}
