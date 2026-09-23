import type { AttemptStatus, CardStatus, GrammarIssueType, SessionStatus } from '@/types/api'

export const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
  generating: 'Gerando perguntas',
  ready: 'Pronta',
  in_progress: 'Em andamento',
  completed: 'Concluída',
  failed: 'Falhou',
}

export const CARD_STATUS_LABELS: Record<CardStatus, string> = {
  active: 'Ativo',
  suspended: 'Suspenso',
  archived: 'Arquivado',
}

export const ATTEMPT_STATUS_LABELS: Record<AttemptStatus, string> = {
  uploaded: 'Enviado',
  probing: 'Verificando áudio',
  transcribing: 'Transcrevendo',
  evaluating: 'Avaliando',
  scheduling: 'Agendando',
  completed: 'Concluído',
  failed: 'Falhou',
}

export const GRAMMAR_ISSUE_LABELS: Record<GrammarIssueType, string> = {
  verb_tense: 'tempo verbal',
  subject_verb_agreement: 'concordância',
  article: 'artigo',
  preposition: 'preposição',
  word_order: 'ordem das palavras',
  plural: 'plural',
  pronoun: 'pronome',
  word_choice: 'escolha de palavra',
  missing_word: 'palavra faltando',
  extra_word: 'palavra a mais',
  agreement: 'concordância (gênero/número)',
  verb_form: 'forma verbal',
  negation: 'negação',
  register: 'registro (tu/vous)',
  other: 'outro',
}

export function grammarIssueLabel(type: string): string {
  return (GRAMMAR_ISSUE_LABELS as Record<string, string>)[type] ?? GRAMMAR_ISSUE_LABELS.other
}
