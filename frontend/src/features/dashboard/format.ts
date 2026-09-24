import { format, parseISO } from 'date-fns'
import { ptBR } from 'date-fns/locale/pt-BR'

const intNumber = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const oneDecimal = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export function fmtInt(value: number | null | undefined): string {
  return value == null ? '–' : intNumber.format(value)
}

export function fmtScore(value: number | null | undefined): string {
  return value == null ? '–' : oneDecimal.format(value)
}

export function fmtSigned(value: number | null | undefined, decimals = 0): string {
  if (value == null) return '–'
  const abs = decimals ? oneDecimal.format(Math.abs(value)) : intNumber.format(Math.abs(value))
  if (value > 0) return `+${abs}`
  if (value < 0) return `−${abs}`
  return decimals ? oneDecimal.format(0) : '0'
}

export function fmtDay(iso: string, pattern = 'd MMM'): string {
  return format(parseISO(iso), pattern, { locale: ptBR })
}

export function fmtWeek(iso: string): string {
  return `sem. ${format(parseISO(iso), 'd MMM', { locale: ptBR })}`
}

/** `7` → "7 s"; `12.5` with one decimal → "12,5 s"; null → "–". */
export function fmtSeconds(seconds: number | null | undefined, decimals = 0): string {
  if (seconds == null) return '–'
  const formatted = decimals ? oneDecimal.format(seconds) : intNumber.format(seconds)
  return `${formatted} s`
}

export function fmtMinutes(seconds: number | null | undefined): string {
  if (!seconds) return '0 min'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

export const MATURITY_LABELS: Record<string, string> = {
  new: 'Novo',
  learning: 'Aprendendo',
  mature: 'Maduro',
  suspended: 'Suspenso',
}

export const AXIS_LABELS = {
  structure: 'Estrutura',
  grammar: 'Gramática',
  fluency: 'Fluência',
} as const

export const ISSUE_TYPE_LABELS: Record<string, string> = {
  verb_tense: 'Tempo verbal',
  subject_verb_agreement: 'Concordância',
  article: 'Artigo',
  preposition: 'Preposição',
  word_order: 'Ordem das palavras',
  plural: 'Plural',
  pronoun: 'Pronome',
  word_choice: 'Escolha de palavra',
  missing_word: 'Palavra faltando',
  extra_word: 'Palavra a mais',
  agreement: 'Concordância (gênero/número)',
  verb_form: 'Forma verbal',
  negation: 'Negação',
  register: 'Registro (tu/vous)',
  other: 'Outro',
}
