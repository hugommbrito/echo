import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/cn'
import { formatNumber, formatSigned } from '@/lib/format'
import { languageMeta } from '@/lib/languages'
import { probePassed } from '@/lib/levels'
import type { Attempt, Card } from '@/types/api'

export interface LevelDeltaProps {
  attempt: Attempt
  card: Card
}

/** "+20 · 1.170 · A2" with probe notes; or why nothing changed. */
export function LevelDelta({ attempt, card }: LevelDeltaProps) {
  if (attempt.insufficient_speech) return null

  if (!attempt.counts_for_scheduling) {
    return (
      <Alert>
        <AlertDescription>
          Esta tentativa não altera o agendamento nem o nível (já houve uma tentativa hoje).
        </AlertDescription>
      </Alert>
    )
  }

  const change = attempt.level_change
  if (!change) return null

  const positive = change.delta > 0
  const negative = change.delta < 0
  const bandChanged = change.band_before !== change.band_after
  const isProbe = card.probe !== 'none'
  const passed = probePassed(change.actual)

  return (
    <section aria-label="Variação de nível" className="rounded-2xl border border-border bg-surface p-5">
      <p className="text-xs uppercase tracking-wide text-fg-muted">
        Seu nível {languageMeta(card.language).inPhrase}
      </p>
      <p className="mt-1 flex flex-wrap items-baseline gap-x-3 text-display text-4xl tabular">
        <span
          className={cn(
            positive && 'text-success',
            negative && 'text-danger',
            !positive && !negative && 'text-fg-muted',
          )}
        >
          {formatSigned(change.delta)}
        </span>
        <span aria-hidden="true" className="text-fg-muted">
          ·
        </span>
        <span>{formatNumber(change.rating_after)}</span>
        <span aria-hidden="true" className="text-fg-muted">
          ·
        </span>
        <span className="text-level-accent">{change.band_after}</span>
      </p>
      <p className="mt-2 text-sm text-fg-muted">
        {bandChanged
          ? positive
            ? `Você subiu de ${change.band_before} para ${change.band_after}.`
            : `Você voltou de ${change.band_before} para ${change.band_after}.`
          : `Antes: ${formatNumber(change.rating_before)}.`}
        {isProbe ? (
          <>
            {' '}
            <span className={cn('font-medium', passed ? 'text-success' : 'text-danger')}>
              {passed ? 'Sonda acertada' : 'Sonda errada'}
            </span>
            {card.probe === 'above'
              ? passed
                ? ' — você respondeu bem uma pergunta acima do seu nível.'
                : ' — a pergunta estava acima do seu nível; pouca penalidade.'
              : passed
                ? ' — pergunta abaixo do seu nível; pouco ganho.'
                : ' — a pergunta estava abaixo do seu nível.'}
          </>
        ) : null}
      </p>
    </section>
  )
}
