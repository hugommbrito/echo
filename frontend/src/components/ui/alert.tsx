import { cva, type VariantProps } from 'class-variance-authority'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

const alertVariants = cva(
  'relative flex w-full gap-3 rounded-xl border p-4 text-sm [&>svg]:mt-0.5 [&>svg]:size-4 [&>svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'border-border bg-surface text-fg [&>svg]:text-fg-muted',
        destructive: 'border-danger/40 bg-danger/10 text-fg [&>svg]:text-danger',
        warning: 'border-warning/40 bg-warning/10 text-fg [&>svg]:text-warning',
        success: 'border-success/40 bg-success/10 text-fg [&>svg]:text-success',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

const ICONS = {
  default: Info,
  destructive: XCircle,
  warning: AlertTriangle,
  success: CheckCircle2,
} as const

export interface AlertProps extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof alertVariants> {
  hideIcon?: boolean
}

export function Alert({ className, variant, hideIcon = false, children, ...props }: AlertProps) {
  const Icon = ICONS[variant ?? 'default']
  return (
    <div role="alert" className={cn(alertVariants({ variant }), className)} {...props}>
      {hideIcon ? null : <Icon aria-hidden="true" />}
      <div className="min-w-0 flex-1 space-y-1">{children}</div>
    </div>
  )
}

export function AlertTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn('font-semibold leading-tight', className)} {...props} />
}

export function AlertDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <div className={cn('text-sm text-fg-muted [&_p]:leading-relaxed', className)} {...props} />
}
