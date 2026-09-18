import { differenceInCalendarDays, format, isValid, parseISO, startOfDay } from 'date-fns'
import { ptBR } from 'date-fns/locale/pt-BR'

const NUMBER = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })

function toDate(value: string | Date): Date | null {
  const date = typeof value === 'string' ? parseISO(value) : value
  return isValid(date) ? date : null
}

/** `1170` → "1.170" */
export function formatNumber(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = typeof value === 'string' ? Number(value) : value
  return Number.isFinite(n) ? NUMBER.format(n) : '—'
}

/** `"3.40"` → "3,4" (digits configurable) */
export function formatDecimal(value: number | string | null | undefined, digits = 1): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** Signed integer with pt-BR grouping: `20` → "+20", `-3` → "−3", `0` → "0". */
export function formatSigned(value: number): string {
  if (value > 0) return `+${NUMBER.format(value)}`
  if (value < 0) return `−${NUMBER.format(Math.abs(value))}`
  return '0'
}

/** ISO date/datetime → "16 de set." */
export function formatDateShort(value: string | Date | null | undefined): string {
  if (!value) return '—'
  const date = toDate(value)
  return date ? format(date, "d 'de' MMM", { locale: ptBR }) : '—'
}

/** ISO date/datetime → "16 de setembro de 2026" */
export function formatDateLong(value: string | Date | null | undefined): string {
  if (!value) return '—'
  const date = toDate(value)
  return date ? format(date, "d 'de' MMMM 'de' yyyy", { locale: ptBR }) : '—'
}

/** ISO date/datetime → "terça-feira, 16 de setembro" */
export function formatWeekdayDate(value: string | Date | null | undefined): string {
  if (!value) return '—'
  const date = toDate(value)
  return date ? format(date, "EEEE, d 'de' MMMM", { locale: ptBR }) : '—'
}

/** ISO datetime → "16/09/2026 14:20" */
export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return '—'
  const date = toDate(value)
  return date ? format(date, 'dd/MM/yyyy HH:mm', { locale: ptBR }) : '—'
}

/**
 * Relative day description in pt-BR based on calendar days:
 * "hoje", "amanhã", "ontem", "em 6 dias", "há 3 dias".
 */
export function formatRelativeDays(
  value: string | Date | null | undefined,
  today: Date = new Date(),
): string {
  if (!value) return '—'
  const date = toDate(value)
  if (!date) return '—'
  const diff = differenceInCalendarDays(startOfDay(date), startOfDay(today))
  if (diff === 0) return 'hoje'
  if (diff === 1) return 'amanhã'
  if (diff === -1) return 'ontem'
  if (diff > 1) return `em ${diff} dias`
  return `há ${Math.abs(diff)} dias`
}

/** Seconds → "m:ss" (e.g. `65.4` → "1:05"). */
export function formatDuration(seconds: number | string | null | undefined): string {
  const n = typeof seconds === 'string' ? Number(seconds) : seconds
  if (n === null || n === undefined || !Number.isFinite(n) || n < 0) return '0:00'
  const total = Math.floor(n)
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  return `${minutes}:${rest.toString().padStart(2, '0')}`
}

/** "dia" / "dias" */
export function pluralDays(n: number): string {
  return n === 1 ? '1 dia' : `${formatNumber(n)} dias`
}

/** Generic pt-BR pluralizer: plural(2, 'hesitação', 'hesitações') → "2 hesitações". */
export function plural(n: number, singular: string, pluralForm: string): string {
  return `${formatNumber(n)} ${n === 1 ? singular : pluralForm}`
}
