import { History } from 'lucide-react'

import { useCardHistory } from '@/api/cards'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AudioPlayer } from '@/components/ui/AudioPlayer'
import { Badge } from '@/components/ui/badge'
import { ScorePill } from '@/components/ui/ScorePill'
import { Skeleton } from '@/components/ui/skeleton'
import { AXES } from '@/lib/colors'
import { formatDateShort, formatDecimal, formatDuration } from '@/lib/format'
import { ATTEMPT_STATUS_LABELS } from '@/lib/labels'
import type { Attempt } from '@/types/api'

export interface AttemptHistoryProps {
  cardId: string
  /** Hide this attempt (usually the one being shown above). */
  excludeAttemptId?: string
  title?: string
  defaultOpen?: boolean
}

export function AttemptHistory({
  cardId,
  excludeAttemptId,
  title = 'Tentativas anteriores',
  defaultOpen = false,
}: AttemptHistoryProps) {
  const history = useCardHistory(cardId)
  const attempts = (history.data ?? []).filter((a) => a.id !== excludeAttemptId)

  return (
    <section aria-label={title} className="rounded-2xl border border-border bg-surface">
      <details open={defaultOpen} className="group">
        <summary className="flex cursor-pointer select-none items-center gap-2 px-5 py-3 text-sm font-medium">
          <History className="size-4 text-fg-muted" aria-hidden="true" />
          {title}
          {history.data ? <span className="text-fg-muted tabular">({attempts.length})</span> : null}
        </summary>
        <div className="border-t border-border">
          {history.isPending ? (
            <div className="space-y-2 p-5">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : history.isError ? (
            <Alert variant="destructive" className="m-4">
              <AlertDescription>Não foi possível carregar o histórico.</AlertDescription>
            </Alert>
          ) : attempts.length === 0 ? (
            <p className="p-5 text-sm text-fg-muted">Nenhuma tentativa anterior para esta pergunta.</p>
          ) : (
            <ul className="divide-y divide-border">
              {attempts.map((attempt) => (
                <AttemptRow key={attempt.id} attempt={attempt} />
              ))}
            </ul>
          )}
        </div>
      </details>
    </section>
  )
}

function AttemptRow({ attempt }: { attempt: Attempt }) {
  const evaluation = attempt.evaluation
  const showScores = attempt.status === 'completed' && !attempt.insufficient_speech && evaluation
  return (
    <li>
      <details className="group/row">
        <summary className="flex cursor-pointer select-none flex-wrap items-center gap-2 px-5 py-3 text-sm">
          <span className="font-medium">{formatDateShort(attempt.attempted_on)}</span>
          <span className="text-fg-muted">#{attempt.attempt_number}</span>
          {showScores ? (
            <span className="flex gap-1">
              {AXES.map((axis) => (
                <ScorePill key={axis} axis={axis} score={evaluation[axis].score} size="sm" />
              ))}
            </span>
          ) : attempt.insufficient_speech ? (
            <Badge variant="warning">fala insuficiente</Badge>
          ) : attempt.status !== 'completed' ? (
            <Badge variant={attempt.status === 'failed' ? 'danger' : 'default'}>
              {ATTEMPT_STATUS_LABELS[attempt.status]}
            </Badge>
          ) : null}
          {!attempt.counts_for_scheduling &&
          attempt.status === 'completed' &&
          !attempt.insufficient_speech ? (
            <Badge variant="outline">não conta</Badge>
          ) : null}
          <span className="ml-auto text-xs text-fg-muted tabular">
            {attempt.audio_duration_seconds ? formatDuration(attempt.audio_duration_seconds) : ''}
          </span>
        </summary>
        <div className="space-y-3 px-5 pb-4">
          <AudioPlayer
            src={attempt.audio_url}
            mimeType={attempt.audio_mime}
            label={`Gravação de ${formatDateShort(attempt.attempted_on)}`}
          />
          {attempt.transcript_text ? (
            <p className="text-sm leading-relaxed text-fg-muted" lang="en">
              {attempt.transcript_text}
            </p>
          ) : null}
          {showScores ? (
            <p className="text-xs text-fg-muted tabular">
              Composta {formatDecimal(evaluation.composite_score, 2)}
            </p>
          ) : null}
        </div>
      </details>
    </li>
  )
}
