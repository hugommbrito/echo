import { ArrowDown, ArrowUp } from 'lucide-react'
import type { ReactNode } from 'react'

import { formatNumber } from '@/lib/format'
import { cn } from '@/lib/cn'
import type { CefrBand, Probe } from '@/types/api'

export interface LevelBadgeProps {
  band: CefrBand | string
  probe?: Probe | null
  /** Optional ELO rating, shown as "B1 · 1.240". */
  rating?: number | null
  /** Leading slot, e.g. a `LanguageTag` ("EN · B1 · 1.240"). */
  tag?: ReactNode
  size?: 'sm' | 'md'
  className?: string
}

/** "B1" (+ "sonda ↑ / ↓" when the card probes above/below the learner's level). */
export function LevelBadge({ band, probe = 'none', rating, tag, size = 'sm', className }: LevelBadgeProps) {
  const isProbe = probe === 'above' || probe === 'below'
  const probeText = probe === 'above' ? 'sonda ↑' : probe === 'below' ? 'sonda ↓' : null
  const ProbeIcon = probe === 'above' ? ArrowUp : ArrowDown
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border font-semibold tabular',
        size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        isProbe ? 'border-level-accent/40 text-level-accent' : 'border-border bg-surface text-fg',
        className,
      )}
      style={
        isProbe ? { backgroundColor: 'color-mix(in srgb, var(--level-accent) 10%, transparent)' } : undefined
      }
      title={
        probeText
          ? `Nível ${band} · ${probeText === 'sonda ↑' ? 'sondagem acima do seu nível' : 'sondagem abaixo do seu nível'}`
          : `Nível ${band}`
      }
    >
      {tag ? (
        <>
          {tag}
          <span aria-hidden="true" className="opacity-50">
            ·
          </span>
        </>
      ) : null}
      <span>{band}</span>
      {rating !== undefined && rating !== null ? (
        <>
          <span aria-hidden="true" className="opacity-50">
            ·
          </span>
          <span className="font-medium">{formatNumber(rating)}</span>
        </>
      ) : null}
      {probeText ? (
        <>
          <span aria-hidden="true" className="opacity-50">
            ·
          </span>
          <span className="inline-flex items-center gap-0.5 font-medium">
            sonda <ProbeIcon className="size-3" aria-hidden="true" />
            <span className="sr-only">{probe === 'above' ? 'acima' : 'abaixo'}</span>
          </span>
        </>
      ) : null}
    </span>
  )
}
