import { Loader2 } from 'lucide-react'

import { cn } from '@/lib/cn'

export interface SpinnerProps {
  className?: string
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

const SIZES = { sm: 'size-4', md: 'size-6', lg: 'size-10' } as const

export function Spinner({ className, label = 'Carregando…', size = 'md' }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn('inline-flex items-center justify-center text-fg-muted', className)}
    >
      <Loader2 className={cn('animate-spin', SIZES[size])} aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
  )
}
