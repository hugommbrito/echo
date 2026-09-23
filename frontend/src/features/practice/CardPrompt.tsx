import { isBefore, parseISO, startOfDay } from 'date-fns'

import { Badge } from '@/components/ui/badge'
import { LanguageTag } from '@/components/ui/LanguageTag'
import { LevelBadge } from '@/components/ui/LevelBadge'
import { MaturityBadge } from '@/components/ui/MaturityBadge'
import { cn } from '@/lib/cn'
import { formatDateShort } from '@/lib/format'
import { languageMeta } from '@/lib/languages'
import type { Card, QueueItem } from '@/types/api'

export interface CardPromptProps {
  card: Card
  kind?: QueueItem['kind']
  origin?: QueueItem['origin']
  dueDate?: string | null
  compact?: boolean
  className?: string
}

function kindLabel(
  kind: QueueItem['kind'] | undefined,
  origin: QueueItem['origin'] | undefined,
  dueDate: string | null | undefined,
): string | null {
  if (kind === 'new') return origin === 'carried_over' ? 'Novo · veio de um dia anterior' : 'Novo'
  if (kind === 'due') {
    if (!dueDate) return 'Revisão'
    const due = startOfDay(parseISO(dueDate))
    const today = startOfDay(new Date())
    return isBefore(due, today) ? `Revisão (venceu em ${formatDateShort(dueDate)})` : 'Revisão (vence hoje)'
  }
  return null
}

export function CardPrompt({ card, kind, origin, dueDate, compact = false, className }: CardPromptProps) {
  const label = kindLabel(kind, origin, dueDate)
  const lang = languageMeta(card.language).htmlLang
  return (
    <article className={cn('space-y-3', className)} aria-label="Pergunta" data-language={card.language}>
      <div className="flex flex-wrap items-center gap-2">
        <LanguageTag code={card.language} />
        <Badge variant="outline">
          {card.category.name}
          {card.category.scope === 'personal' ? <span className="text-level-accent">· pessoal</span> : null}
        </Badge>
        <MaturityBadge maturity={card.maturity} />
        <LevelBadge band={card.cefr_level} probe={card.probe} />
        {label ? <Badge variant={kind === 'due' ? 'primary' : 'default'}>{label}</Badge> : null}
      </div>
      {card.scenario ? (
        <p className={cn('italic text-fg-muted', compact ? 'text-sm' : 'text-base')} lang={lang}>
          {card.scenario}
        </p>
      ) : null}
      <h2
        className={cn('text-display leading-snug', compact ? 'text-xl sm:text-2xl' : 'text-2xl sm:text-4xl')}
        lang={lang}
      >
        {card.question_text}
      </h2>
    </article>
  )
}
