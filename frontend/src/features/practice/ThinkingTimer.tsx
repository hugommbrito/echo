import { Timer } from 'lucide-react'

import { cn } from '@/lib/cn'
import { formatSeconds } from '@/lib/format'
import { ZONE_COLORS, ZONE_LABELS, zoneFor } from '@/lib/thinkingTime'

export interface ThinkingTimerProps {
  seconds: number
  baseline: number | null
  running: boolean
  isDefaultBaseline?: boolean
}

/** Live "time to start" line: counts up in the zone colour, freezes at the first press on record. */
export function ThinkingTimer({ seconds, baseline, running, isDefaultBaseline = false }: ThinkingTimerProps) {
  const zone = zoneFor(seconds, baseline)
  const reference =
    baseline == null
      ? 'ainda sem referência'
      : `${isDefaultBaseline ? 'referência inicial' : 'sua referência'} ${formatSeconds(baseline)}`
  return (
    <p
      role="timer"
      aria-label="Tempo para começar"
      aria-live={running ? 'off' : 'polite'}
      className={cn(
        'flex flex-wrap items-center gap-x-2 text-sm tabular',
        zone ? ZONE_COLORS[zone].text : 'text-fg-muted',
      )}
    >
      <Timer className="size-4" aria-hidden="true" />
      <span>
        Tempo para começar: <span className="font-semibold">{formatSeconds(seconds)}</span>
      </span>
      <span className="text-fg-muted">· {reference}</span>
      {!running && zone ? <span>· {ZONE_LABELS[zone]}</span> : null}
    </p>
  )
}
