import { isBefore, parseISO, startOfDay } from 'date-fns'
import { Eye } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LanguageTag } from '@/components/ui/LanguageTag'
import { LevelBadge } from '@/components/ui/LevelBadge'
import { MaturityBadge } from '@/components/ui/MaturityBadge'
import { cn } from '@/lib/cn'
import { formatDateShort } from '@/lib/format'
import { languageMeta } from '@/lib/languages'
import type { Card, QueueItem, QuestionMode } from '@/types/api'

export interface CardPromptProps {
  card: Card
  kind?: QueueItem['kind']
  origin?: QueueItem['origin']
  dueDate?: string | null
  compact?: boolean
  className?: string
  /** How the question is presented (default: text). In `listen` the text stays hidden. */
  mode?: QuestionMode
  /** Listen mode: the learner asked to see the text (controlled by the parent). */
  textRevealed?: boolean
  onRevealText?: () => void
  /** The "Ouvir pergunta" row, rendered under the question (not in `compact`). */
  audio?: ReactNode
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

export function CardPrompt({
  card,
  kind,
  origin,
  dueDate,
  compact = false,
  className,
  mode = 'read',
  textRevealed = false,
  onRevealText,
  audio,
}: CardPromptProps) {
  const label = kindLabel(kind, origin, dueDate)
  const lang = languageMeta(card.language).htmlLang
  // Hidden text is absent from the DOM (not just visually hidden) so it cannot be read aloud early.
  const hideText = mode === 'listen' && !textRevealed && !compact
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
      {hideText ? (
        <div className="space-y-3 rounded-2xl border border-dashed border-border bg-surface-muted/40 p-5">
          <p className="text-sm text-fg-muted">Ouça a pergunta e responda. Se precisar, mostre o texto.</p>
          <Button type="button" variant="outline" size="sm" onClick={onRevealText}>
            <Eye /> Mostrar texto
          </Button>
        </div>
      ) : (
        <h2
          className={cn(
            'text-display leading-snug',
            compact ? 'text-xl sm:text-2xl' : 'text-2xl sm:text-4xl',
          )}
          lang={lang}
        >
          {card.question_text}
        </h2>
      )}
      {audio && !compact ? <div className="pt-1">{audio}</div> : null}
    </article>
  )
}
