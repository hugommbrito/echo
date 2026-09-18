import { AXIS_COLORS, type Axis } from '@/lib/colors'
import { cn } from '@/lib/cn'

export interface ScoreBarProps {
  axis: Axis
  /** 1–5 (may be a decimal for averages). */
  score: number
  max?: number
  label?: string
  className?: string
}

/** Segmented bar (5 blocks) in the axis color with a big number beside it. */
export function ScoreBar({ axis, score, max = 5, label, className }: ScoreBarProps) {
  const token = AXIS_COLORS[axis]
  const filled = Math.max(0, Math.min(max, score))
  const segments = Array.from({ length: max }, (_, i) => Math.max(0, Math.min(1, filled - i)))
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={filled}
        aria-label={label ?? token.label}
        className="flex flex-1 gap-1"
      >
        {segments.map((fill, i) => (
          <span key={i} className="h-2 flex-1 overflow-hidden rounded-sm bg-surface-muted">
            <span
              className="block h-full rounded-sm"
              style={{ width: `${fill * 100}%`, backgroundColor: token.css }}
            />
          </span>
        ))}
      </div>
      <span className="text-display text-2xl tabular" style={{ color: token.css }}>
        {Number.isInteger(score) ? score : score.toFixed(1).replace('.', ',')}
      </span>
    </div>
  )
}
