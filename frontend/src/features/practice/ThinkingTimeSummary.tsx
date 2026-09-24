import { Headphones, Timer } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/cn'
import { formatSeconds } from '@/lib/format'
import { ZONE_COLORS, ZONE_LABELS, toSeconds, zoneFor } from '@/lib/thinkingTime'
import type { Attempt } from '@/types/api'

/** Result panel: "Tempo para começar: 4,2 s · sua referência 6 s · no ritmo" + listen telemetry. */
export function ThinkingTimeSummary({ attempt }: { attempt: Attempt }) {
  const seconds = toSeconds(attempt.thinking_seconds)
  const baseline = toSeconds(attempt.thinking_baseline_seconds)
  const mode = attempt.question_mode
  if (seconds == null && mode == null) return null
  const zone = seconds != null ? zoneFor(seconds, baseline) : null
  return (
    <section
      aria-label="Tempo para começar"
      className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border border-border bg-surface-muted/60 p-4 text-sm"
    >
      <Timer className="size-5 text-fg-muted" aria-hidden="true" />
      <p className="tabular">
        Tempo para começar:{' '}
        {seconds == null ? (
          <span className="text-fg-muted">— (nova tentativa da mesma pergunta)</span>
        ) : (
          <>
            <strong className={cn(zone && ZONE_COLORS[zone].text)}>{formatSeconds(seconds, 1)}</strong>
            <span className="text-fg-muted">
              {baseline != null ? ` · sua referência ${formatSeconds(baseline)}` : ' · ainda sem referência'}
            </span>
            {zone ? (
              <span className={cn('ml-2 font-medium', ZONE_COLORS[zone].text)}>{ZONE_LABELS[zone]}</span>
            ) : null}
          </>
        )}
      </p>
      {mode && mode !== 'read' ? (
        <span className="flex flex-wrap gap-1.5">
          <Badge variant="outline">
            <Headphones className="size-3" aria-hidden="true" />
            {attempt.audio_replays > 0 ? `ouviu ${attempt.audio_replays}×` : 'não ouviu o áudio'}
          </Badge>
          {mode === 'listen' ? (
            <Badge variant="outline">{attempt.text_revealed ? 'texto revelado' : 'só de ouvido'}</Badge>
          ) : null}
        </span>
      ) : null}
    </section>
  )
}
