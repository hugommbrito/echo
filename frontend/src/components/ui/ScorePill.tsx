import { AXIS_COLORS, type Axis } from '@/lib/colors'
import { cn } from '@/lib/cn'

export interface ScorePillProps {
  axis: Axis
  /** 1–5 */
  score: number
  size?: 'sm' | 'md' | 'lg'
  /** Show the axis label next to the number. */
  showLabel?: boolean
  className?: string
}

const SIZES = {
  sm: 'h-6 min-w-6 px-1.5 text-xs',
  md: 'h-8 min-w-8 px-2 text-sm',
  lg: 'h-12 min-w-12 px-3 text-2xl',
} as const

/** Score 1–5 painted with the fixed color of its axis. */
export function ScorePill({ axis, score, size = 'md', showLabel = false, className }: ScorePillProps) {
  const token = AXIS_COLORS[axis]
  return (
    <span
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-full font-semibold tabular',
        SIZES[size],
        className,
      )}
      style={{
        color: token.css,
        backgroundColor: `color-mix(in srgb, ${token.css} 14%, transparent)`,
      }}
      aria-label={`${token.label}: nota ${score} de 5`}
      title={`${token.label}: ${score}/5`}
    >
      {showLabel ? <span className="text-xs font-medium opacity-80">{token.label}</span> : null}
      <span>{score}</span>
    </span>
  )
}
