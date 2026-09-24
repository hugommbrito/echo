import { describe, expect, it } from 'vitest'

import type { User } from '@/types/api'

import { baselineFor, toSeconds, zoneFor } from './thinkingTime'

describe('zoneFor', () => {
  it('is green up to the reference, yellow up to 1.5×, red above — with no lower bound', () => {
    expect(zoneFor(0, 6)).toBe('good')
    expect(zoneFor(6, 6)).toBe('good')
    expect(zoneFor(9, 6)).toBe('ok')
    expect(zoneFor(9.01, 6)).toBe('slow')
    expect(zoneFor(60, 6)).toBe('slow')
  })

  it('stays neutral without a usable reference', () => {
    expect(zoneFor(5, null)).toBeNull()
    expect(zoneFor(5, undefined)).toBeNull()
    expect(zoneFor(5, 0)).toBeNull()
    expect(zoneFor(5, Number.NaN)).toBeNull()
  })
})

describe('baselineFor', () => {
  const me = {
    languages: [
      { code: 'en', thinking_time: { baseline_seconds: 6, samples: 0, is_default: true } },
      { code: 'fr', thinking_time: { baseline_seconds: 9.5, samples: 12, is_default: false } },
    ],
  } as unknown as User

  it('finds the profile of the card language', () => {
    expect(baselineFor(me, 'fr')).toEqual({ baseline_seconds: 9.5, samples: 12, is_default: false })
    expect(baselineFor(me, 'en')?.is_default).toBe(true)
  })

  it('is null when the language has no profile or `me` is not loaded yet', () => {
    expect(baselineFor(me, 'es')).toBeNull()
    expect(baselineFor(undefined, 'en')).toBeNull()
  })
})

describe('toSeconds', () => {
  it('accepts numbers and legacy decimal strings', () => {
    expect(toSeconds(12.5)).toBe(12.5)
    expect(toSeconds('12.50')).toBe(12.5)
    expect(toSeconds(0)).toBe(0)
  })

  it('maps empty and invalid values to null', () => {
    expect(toSeconds(null)).toBeNull()
    expect(toSeconds(undefined)).toBeNull()
    expect(toSeconds('')).toBeNull()
    expect(toSeconds('abc')).toBeNull()
  })
})
