import { ArrowRight, CalendarClock } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { MaturityBadge } from '@/components/ui/MaturityBadge'
import { ScorePill } from '@/components/ui/ScorePill'
import { AXES, AXIS_COLORS, type Axis } from '@/lib/colors'
import { formatDateShort, formatDecimal, plural, pluralDays } from '@/lib/format'
import { grammarIssueLabel } from '@/lib/labels'
import { languageMeta } from '@/lib/languages'
import type { Attempt, Evaluation, GrammarIssue, Review } from '@/types/api'

import { ImprovedAnswerButton } from './ImprovedAnswerButton'

export interface EvaluationPanelProps {
  attempt: Attempt
}

export function EvaluationPanel({ attempt }: EvaluationPanelProps) {
  const evaluation = attempt.evaluation
  const lang = languageMeta(attempt.language).htmlLang

  if (attempt.insufficient_speech) {
    return (
      <section aria-label="Avaliação" className="space-y-4">
        <Alert variant="warning">
          <AlertTitle>Não detectamos fala suficiente. Grave de novo.</AlertTitle>
          <AlertDescription>
            Esta tentativa não altera o agendamento nem o nível. Fale por alguns segundos, de preferência em
            um lugar silencioso.
          </AlertDescription>
        </Alert>
        <Transcript attempt={attempt} />
      </section>
    )
  }

  if (!evaluation) {
    return (
      <Alert>
        <AlertDescription>A avaliação ainda não está disponível.</AlertDescription>
      </Alert>
    )
  }

  return (
    <section aria-label="Avaliação" className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-fg-muted">Nota composta</p>
          <p className="text-display text-5xl tabular">{formatDecimal(evaluation.composite_score, 1)}</p>
        </div>
        <div className="flex gap-2">
          {AXES.map((axis) => (
            <ScorePill key={axis} axis={axis} score={evaluation[axis].score} size="lg" />
          ))}
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        {AXES.map((axis) => (
          <AxisBlock key={axis} axis={axis} evaluation={evaluation} />
        ))}
      </div>

      {evaluation.grammar.issues.length > 0 ? (
        <GrammarIssues issues={evaluation.grammar.issues} lang={lang} />
      ) : null}

      {evaluation.key_points.length > 0 ? (
        <section className="rounded-2xl border border-border bg-surface p-5">
          <h3 className="text-sm font-semibold">O que uma resposta completa costuma cobrir</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm" lang="en">
            {evaluation.key_points.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <ImprovedAnswerButton attempt={attempt} />

      <Transcript attempt={attempt} />
    </section>
  )
}

function AxisBlock({ axis, evaluation }: { axis: Axis; evaluation: Evaluation }) {
  const token = AXIS_COLORS[axis]
  const data = evaluation[axis]
  const markers = axis === 'fluency' ? evaluation.fluency.markers : null
  return (
    <section
      aria-label={token.label}
      className="rounded-2xl border bg-surface p-5"
      style={{ borderColor: `color-mix(in srgb, ${token.css} 35%, transparent)` }}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold" style={{ color: token.css }}>
          {token.label}
        </h3>
        <ScorePill axis={axis} score={data.score} />
      </div>
      <p className="mt-3 text-sm leading-relaxed">{data.feedback}</p>
      {markers ? (
        <p className="mt-3 text-xs text-fg-muted">
          {plural(markers.fillers, 'hesitação', 'hesitações')} ·{' '}
          {plural(markers.false_starts, 'recomeço', 'recomeços')} ·{' '}
          {plural(markers.repetitions, 'repetição', 'repetições')}
        </p>
      ) : null}
    </section>
  )
}

function GrammarIssues({ issues, lang }: { issues: GrammarIssue[]; lang: string }) {
  const token = AXIS_COLORS.grammar
  return (
    <section aria-label="Correções de gramática" className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-sm font-semibold" style={{ color: token.css }}>
        Correções
      </h3>
      <ul className="mt-3 divide-y divide-border">
        {issues.map((issue, i) => (
          <li key={i} className="space-y-1 py-3 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-center gap-2 text-sm" lang={lang}>
              <span className="line-through decoration-danger/60 text-fg-muted">{issue.quote}</span>
              <ArrowRight className="size-4 shrink-0 text-fg-muted" aria-hidden="true" />
              <span className="font-medium">{issue.correction}</span>
              <Badge variant="warning" className="ml-auto">
                {grammarIssueLabel(issue.type)}
              </Badge>
            </div>
            {issue.explanation ? <p className="text-xs text-fg-muted">{issue.explanation}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  )
}

function Transcript({ attempt }: { attempt: Attempt }) {
  if (!attempt.transcript_text) return null
  const lang = languageMeta(attempt.language).htmlLang
  return (
    <details className="group rounded-2xl border border-border bg-surface">
      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium marker:text-fg-muted">
        Transcrição
        {attempt.word_count !== null ? (
          <span className="ml-2 font-normal text-fg-muted tabular">
            {plural(attempt.word_count, 'palavra', 'palavras')}
            {attempt.words_per_minute ? ` · ${formatDecimal(attempt.words_per_minute, 0)} ppm` : ''}
          </span>
        ) : null}
      </summary>
      <p
        className="whitespace-pre-line border-t border-border px-5 py-4 text-sm leading-relaxed text-fg-muted"
        lang={lang}
      >
        {attempt.transcript_text}
      </p>
    </details>
  )
}

/** "Próxima revisão em 6 dias (22 de set.)" + maturity change. */
export function ReviewSummary({ review }: { review: Review }) {
  const changed = review.maturity_before !== review.maturity_after
  return (
    <section
      aria-label="Agendamento"
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-border bg-surface-muted/60 p-4 text-sm"
    >
      <CalendarClock className="size-5 text-fg-muted" aria-hidden="true" />
      <p>
        Próxima revisão em <strong className="tabular">{pluralDays(review.interval_after)}</strong>{' '}
        <span className="text-fg-muted">({formatDateShort(review.due_after)})</span>
      </p>
      <p className="flex items-center gap-1.5">
        <MaturityBadge maturity={review.maturity_before} />
        {changed ? (
          <>
            <ArrowRight className="size-3.5 text-fg-muted" aria-hidden="true" />
            <MaturityBadge maturity={review.maturity_after} />
          </>
        ) : null}
      </p>
      <p className="text-xs text-fg-muted tabular">
        facilidade {formatDecimal(review.ease_before, 2)} → {formatDecimal(review.ease_after, 2)} · qualidade{' '}
        {review.quality}/5
      </p>
    </section>
  )
}
