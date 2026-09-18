import { describe, expect, it } from 'vitest'

import {
  formatDateShort,
  formatDecimal,
  formatDuration,
  formatNumber,
  formatRelativeDays,
  formatSigned,
  plural,
  pluralDays,
} from './format'

describe('formatNumber', () => {
  it('groups thousands with a dot (pt-BR)', () => {
    expect(formatNumber(1170)).toBe('1.170')
    expect(formatNumber('1240')).toBe('1.240')
    expect(formatNumber(999)).toBe('999')
  })
  it('returns a dash for empty values', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(undefined)).toBe('—')
    expect(formatNumber('abc')).toBe('—')
  })
})

describe('formatDecimal', () => {
  it('formats decimal strings with a comma', () => {
    expect(formatDecimal('3.40', 1)).toBe('3,4')
    expect(formatDecimal('2.5', 2)).toBe('2,50')
    expect(formatDecimal(4, 1)).toBe('4,0')
  })
})

describe('formatSigned', () => {
  it('adds an explicit sign', () => {
    expect(formatSigned(20)).toBe('+20')
    expect(formatSigned(-3)).toBe('−3')
    expect(formatSigned(0)).toBe('0')
    expect(formatSigned(1170)).toBe('+1.170')
  })
})

describe('formatDuration', () => {
  it('renders m:ss', () => {
    expect(formatDuration(0)).toBe('0:00')
    expect(formatDuration(5)).toBe('0:05')
    expect(formatDuration(65.4)).toBe('1:05')
    expect(formatDuration(300)).toBe('5:00')
    expect(formatDuration('12.9')).toBe('0:12')
  })
  it('handles invalid input', () => {
    expect(formatDuration(null)).toBe('0:00')
    expect(formatDuration(-4)).toBe('0:00')
    expect(formatDuration(Number.NaN)).toBe('0:00')
  })
})

describe('formatRelativeDays', () => {
  const today = new Date(2026, 8, 16) // 16 Sep 2026 (local)
  it('names today, tomorrow and yesterday', () => {
    expect(formatRelativeDays('2026-09-16', today)).toBe('hoje')
    expect(formatRelativeDays('2026-09-17', today)).toBe('amanhã')
    expect(formatRelativeDays('2026-09-15', today)).toBe('ontem')
  })
  it('counts calendar days in both directions', () => {
    expect(formatRelativeDays('2026-09-22', today)).toBe('em 6 dias')
    expect(formatRelativeDays('2026-09-13', today)).toBe('há 3 dias')
  })
  it('returns a dash for missing values', () => {
    expect(formatRelativeDays(null, today)).toBe('—')
  })
})

describe('formatDateShort', () => {
  it('uses the pt-BR month abbreviation', () => {
    // date-fns v4 ptBR abbreviates without a trailing dot
    expect(formatDateShort('2026-09-16')).toBe('16 de set')
    expect(formatDateShort('2026-01-05')).toBe('5 de jan')
  })
})

describe('plural helpers', () => {
  it('pluralises days', () => {
    expect(pluralDays(1)).toBe('1 dia')
    expect(pluralDays(6)).toBe('6 dias')
  })
  it('pluralises arbitrary nouns', () => {
    expect(plural(1, 'hesitação', 'hesitações')).toBe('1 hesitação')
    expect(plural(4, 'hesitação', 'hesitações')).toBe('4 hesitações')
  })
})
