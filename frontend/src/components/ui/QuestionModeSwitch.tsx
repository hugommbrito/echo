import { BookHeadphones, BookOpen, Headphones, type LucideIcon } from 'lucide-react'

import { cn } from '@/lib/cn'
import { QUESTION_MODE_LABELS } from '@/lib/labels'
import type { QuestionMode } from '@/types/api'

const OPTIONS: { value: QuestionMode; icon: LucideIcon }[] = [
  { value: 'read', icon: BookOpen },
  { value: 'listen', icon: Headphones },
  { value: 'both', icon: BookHeadphones },
]

export interface QuestionModeSwitchProps {
  value: QuestionMode
  onChange: (mode: QuestionMode) => void
  disabled?: boolean
  size?: 'sm' | 'md'
  'aria-label'?: string
  className?: string
}

/** Segmented control (same markup as the session's language filter): Ler · Ouvir · Ler e ouvir. */
export function QuestionModeSwitch({
  value,
  onChange,
  disabled = false,
  size = 'md',
  'aria-label': ariaLabel = 'Como ver a pergunta',
  className,
}: QuestionModeSwitchProps) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex flex-wrap rounded-lg border border-border bg-surface p-0.5',
        size === 'sm' ? 'text-xs' : 'text-sm',
        className,
      )}
    >
      {OPTIONS.map(({ value: option, icon: Icon }) => {
        const checked = option === value
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={checked}
            disabled={disabled}
            onClick={() => onChange(option)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md transition-colors disabled:opacity-60',
              size === 'sm' ? 'px-2.5 py-1' : 'px-3 py-1.5',
              checked ? 'bg-bg font-semibold text-fg' : 'text-fg-muted hover:text-fg',
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {QUESTION_MODE_LABELS[option]}
          </button>
        )
      })}
    </div>
  )
}
