/**
 * Hand-written types matching the Echo API contract (`/api/v1`).
 * Dates are ISO `YYYY-MM-DD`, datetimes ISO 8601, decimals arrive as strings ("3.40").
 * Run `npm run gen:types` to compare against the live OpenAPI schema.
 */

export type ISODate = string
export type ISODateTime = string
export type DecimalString = string
export type UUID = string

export type CefrBand = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2'
export type FeedbackLanguage = 'pt-BR' | 'en'
export type Probe = 'none' | 'above' | 'below'
export type CardStatus = 'active' | 'suspended' | 'archived'
export type Maturity = 'new' | 'learning' | 'mature'
export type CategoryScope = 'global' | 'personal'
export type SessionStatus = 'generating' | 'ready' | 'in_progress' | 'completed' | 'failed'
export type AttemptStatus =
  'uploaded' | 'probing' | 'transcribing' | 'evaluating' | 'scheduling' | 'completed' | 'failed'
export type QueueKind = 'new' | 'due'
export type QueueOrigin = 'generated' | 'carried_over'

export type GrammarIssueType =
  | 'verb_tense'
  | 'subject_verb_agreement'
  | 'article'
  | 'preposition'
  | 'word_order'
  | 'plural'
  | 'pronoun'
  | 'word_choice'
  | 'missing_word'
  | 'extra_word'
  | 'other'

// --- Errors -----------------------------------------------------------------

export interface ApiErrorBody {
  detail: string
  code: string
  errors?: Record<string, string[]>
  [extra: string]: unknown
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// --- Auth / profile ----------------------------------------------------------

export interface UserLevel {
  rating: number
  band: CefrBand
  provisional: boolean
  counted_attempts: number
  initial_rating: number
}

export interface User {
  id: UUID
  email: string
  full_name: string
  timezone: string
  feedback_language: FeedbackLanguage
  default_new_cards_per_day: number
  is_staff: boolean
  level: UserLevel
}

export interface UserPatch {
  timezone?: string
  feedback_language?: FeedbackLanguage
  default_new_cards_per_day?: number
}

export interface LoginPayload {
  email: string
  password: string
}

export interface CsrfResponse {
  csrfToken: string
}

// --- Categories --------------------------------------------------------------

export interface Category {
  id: UUID
  slug: string
  name: string
  description: string
  generation_hint: string
  is_active: boolean
  sort_order: number
  scope: CategoryScope
  card_count: number
}

export interface CategoryBrief {
  id: UUID
  slug: string
  name: string
  scope: CategoryScope
}

export interface CategoryCreate {
  slug: string
  name: string
  description?: string
  generation_hint?: string
}

export interface CategoryPatch {
  name?: string
  description?: string
  generation_hint?: string
  is_active?: boolean
}

// --- Cards -------------------------------------------------------------------

export interface Card {
  id: UUID
  category: CategoryBrief
  question_text: string
  scenario: string | null
  key_points: string[]
  cefr_level: CefrBand
  difficulty_rating: number
  probe: Probe
  status: CardStatus
  source: string
  maturity: Maturity
  attempt_count: number
  created_at: ISODateTime
}

export interface SchedulerState {
  maturity: Maturity
  ease_factor: DecimalString
  interval_days: number
  repetitions: number
  lapses: number
  total_reviews: number
  due_date: ISODate | null
  last_reviewed_on: ISODate | null
  last_quality: number | null
}

export interface LastScores {
  attempt_id: UUID
  attempted_on: ISODate
  structure: number
  grammar: number
  fluency: number
  composite: DecimalString
}

export interface CardDetail extends Card {
  scheduler: SchedulerState | null
  last_scores: LastScores | null
}

export interface CardFilters {
  category?: string
  maturity?: Maturity | ''
  level?: CefrBand | ''
  status?: CardStatus | ''
  q?: string
  page?: number
  page_size?: number
}

// --- Sessions ----------------------------------------------------------------

export interface Projection {
  carried_over: number
  to_generate: number
  due_today: number
  overdue: number
  probes: number
  base_level: CefrBand
  total: number
}

export interface SessionProgress {
  new_total: number
  new_done: number
  due_total: number
  due_done: number
  remaining: number
}

export interface Session {
  id: UUID
  session_date: ISODate
  new_cards_target: number
  categories: CategoryBrief[]
  status: SessionStatus
  generation_error: string
  rating_at_start: number
  completed_at: ISODateTime | null
  created_at: ISODateTime
  progress: SessionProgress
  projected: Projection | null
}

export interface SessionCreate {
  category_ids: UUID[]
  new_cards_target: number
}

export interface QueueItem {
  kind: QueueKind
  position: number | null
  origin: QueueOrigin | null
  due_date: ISODate | null
  card: Card
}

// --- Attempts ----------------------------------------------------------------

export interface AttemptAccepted {
  id: UUID
  status: AttemptStatus
}

export interface AxisEvaluation {
  score: number
  feedback: string
}

export interface GrammarIssue {
  quote: string
  correction: string
  type: GrammarIssueType | string
  explanation: string
}

export interface GrammarEvaluation extends AxisEvaluation {
  issues: GrammarIssue[]
}

export interface FluencyMarkers {
  fillers: number
  false_starts: number
  repetitions: number
}

export interface FluencyEvaluation extends AxisEvaluation {
  markers: FluencyMarkers
}

export interface Evaluation {
  structure: AxisEvaluation
  grammar: GrammarEvaluation
  fluency: FluencyEvaluation
  composite_score: DecimalString
  sm2_quality: number
  key_points: string[]
  improved_answer: string | null
  improved_answer_notes: string[]
  model: string
}

export interface Review {
  quality: number
  composite_score: DecimalString
  ease_before: DecimalString
  ease_after: DecimalString
  interval_before: number
  interval_after: number
  due_before: ISODate | null
  due_after: ISODate
  maturity_before: Maturity
  maturity_after: Maturity
  reviewed_on: ISODate
}

export interface LevelChange {
  rating_before: number
  rating_after: number
  delta: number
  expected: DecimalString
  actual: DecimalString
  question_rating: number
  k_factor: number
  band_before: CefrBand
  band_after: CefrBand
  logged_on: ISODate
}

export interface Attempt {
  id: UUID
  status: AttemptStatus
  failure_stage: string
  error_message: string
  card_id: UUID
  session_id: UUID | null
  attempt_number: number
  attempted_on: ISODate
  counts_for_scheduling: boolean
  insufficient_speech: boolean
  audio_url: string | null
  audio_mime: string
  audio_duration_seconds: DecimalString | null
  transcript_text: string
  word_count: number | null
  words_per_minute: DecimalString | null
  transcription_model: string
  evaluation: Evaluation | null
  review: Review | null
  level_change: LevelChange | null
  created_at: ISODateTime
  completed_at: ISODateTime | null
}

export interface ImprovedAnswer {
  improved_answer: string
  notes: string[]
  model: string
  generated_at: ISODateTime
}
