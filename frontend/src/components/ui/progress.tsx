import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

export interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  /** 0–100 */
  value: number
  /** CSS color for the bar (defaults to the primary token). */
  color?: string
  size?: 'sm' | 'md'
  label?: string
}

export function Progress({ value, color, size = 'md', label, className, ...props }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0))
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      aria-label={label}
      className={cn(
        'w-full overflow-hidden rounded-full bg-surface-muted',
        size === 'sm' ? 'h-1.5' : 'h-2.5',
        className,
      )}
      {...props}
    >
      <div
        className="h-full rounded-full transition-[width] duration-300 ease-out"
        style={{ width: `${clamped}%`, backgroundColor: color ?? 'var(--primary)' }}
      />
    </div>
  )
}
