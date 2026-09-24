export type Period = { from: string; to: string; days: number }

export type ScoreSummary = {
  structure_avg: number | null
  grammar_avg: number | null
  fluency_avg: number | null
  composite_avg: number | null
  attempts: number
}

export type Overview = {
  period: Period
  today: {
    answered: number
    new_answered: number
    due_answered: number
    target: number
    session_id: string | null
    session_status: string | null
  }
  due: { today: number; overdue: number; next_7_days: number }
  collection: { total: number; new: number; learning: number; mature: number; suspended: number }
  scores: { period: ScoreSummary; previous_period: ScoreSummary }
  /** One entry per active language (plus a paused one when it is requested explicitly). */
  levels: LevelOverview[]
}

export type LevelOverview = {
  language: string
  rating: number
  band: string
  delta_period: number
  provisional: boolean
  counted_attempts: number
  initial_rating: number
  is_active: boolean
  next_band: { label: string; points_needed: number } | null
}

export type ScoreBucket = ScoreSummary & { bucket_start: string }

export type LevelEvent = {
  date: string
  delta: number
  rating_after: number
  probe: 'above' | 'below'
  hit: boolean
}

export type LevelSeries = {
  language: string
  points: { date: string; rating_after: number }[]
  probes: Record<
    'above' | 'below',
    { answered: number; hits: number; avg_actual: number | null; avg_delta: number | null }
  >
  events: LevelEvent[]
  current: { rating: number; band: string }
  initial_rating: number
  is_active: boolean
}

export type LevelStats = {
  period: Period
  bands: { label: string; min: number; max: number; center: number }[]
  series: LevelSeries[]
}

export type ActivityBucket = {
  bucket_start: string
  new: number
  learning: number
  mature: number
  total: number
  speaking_seconds: number
}

export type Forecast = { days: { date: string; due: number }[]; overdue: number; total: number }

export type Collection = {
  by_maturity: { new: number; learning: number; mature: number; suspended: number }
  by_category: {
    category: { id: string; slug: string; name: string }
    new: number
    learning: number
    mature: number
    total: number
  }[]
  by_level: { language: string; levels: { level: string; count: number }[] }[]
  by_language: {
    language: string
    total: number
    new: number
    learning: number
    mature: number
    suspended: number
  }[]
}

export type GrammarIssues = {
  period: Period
  items: {
    type: string
    count: number
    previous_count: number
    delta: number
    examples: { quote: string; correction: string }[]
  }[]
  total: number
  previous_total: number
}

export type CategoryRow = {
  category: { id: string; slug: string; name: string; scope: 'global' | 'personal' }
  cards: number
  attempts: number
  structure_avg: number | null
  grammar_avg: number | null
  fluency_avg: number | null
  composite_avg: number | null
  trend: { week_start: string; composite_avg: number | null }[]
}

export type HeatmapCell = { date: string; count: number; speaking_seconds: number }

export type ThinkingTimeStats = {
  avg_seconds: number | null
  median_seconds: number | null
  attempts: number
  series: { date: string; median_seconds: number | null; attempts: number }[]
}

export type Advanced = {
  ease: { ease: string; count: number }[]
  intervals: { range: string; count: number }[]
  answer_duration: {
    avg_seconds: number | null
    min_seconds: number | null
    max_seconds: number | null
    attempts: number
  }
  /** Respects the period/category/language filters (the other blocks are all-time). */
  thinking_time?: ThinkingTimeStats | null
}

export type CategoryOption = { id: string; slug: string; name: string; scope: 'global' | 'personal' }

export type PeriodPreset = '7d' | '30d' | '90d' | '1y' | 'all'
