import { MATURITY_COLORS } from '@/lib/colors'
import { cn } from '@/lib/cn'
import type { Maturity } from '@/types/api'

export interface MaturityBadgeProps {
  maturity: Maturity
  className?: string
}

/** Dot in the maturity color + pt-BR label. */
export function MaturityBadge({ maturity, className }: MaturityBadgeProps) {
  const token = MATURITY_COLORS[maturity]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs font-medium text-fg',
        className,
      )}
      title={`Maturidade: ${token.label}`}
    >
      <span
        aria-hidden="true"
        className="size-2 rounded-full ring-1 ring-black/10 dark:ring-white/20"
        style={{ backgroundColor: token.css }}
      />
      {token.label}
    </span>
  )
}
