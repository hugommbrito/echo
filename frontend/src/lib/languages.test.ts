import { describe, expect, it } from 'vitest'

import type { User } from '@/types/api'

import { activeLanguages, isLanguageCode, languageMeta, sortByLanguage } from './languages'

describe('languages registry', () => {
  it('knows English and Canadian French', () => {
    expect(languageMeta('en')).toMatchObject({ label: 'Inglês', short: 'EN', htmlLang: 'en-CA' })
    expect(languageMeta('fr')).toMatchObject({ label: 'Francês', short: 'FR', htmlLang: 'fr-CA' })
    expect(isLanguageCode('fr')).toBe(true)
    expect(isLanguageCode('xx')).toBe(false)
  })

  it('renders an unknown code in ink instead of crashing', () => {
    expect(languageMeta('es')).toMatchObject({ short: 'ES', htmlLang: 'es', colorVar: '--chart-ink' })
  })

  it('sorts by registry order and filters paused profiles', () => {
    expect(sortByLanguage(['fr', 'es', 'en'], (c) => c)).toEqual(['en', 'fr', 'es'])
    const me = {
      languages: [
        { code: 'fr', is_active: true },
        { code: 'en', is_active: false },
      ],
    } as unknown as User
    expect(activeLanguages(me).map((p) => p.code)).toEqual(['fr'])
    expect(activeLanguages(undefined)).toEqual([])
  })
})
