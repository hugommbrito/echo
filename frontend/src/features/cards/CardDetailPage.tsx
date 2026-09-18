import { ArrowLeft, Pause, Play } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { useCard, useSuspendCard, useUnsuspendCard } from '@/api/cards'
import { isApiError } from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LevelBadge } from '@/components/ui/LevelBadge'
import { MaturityBadge } from '@/components/ui/MaturityBadge'
import { ScorePill } from '@/components/ui/ScorePill'
import { Skeleton } from '@/components/ui/skeleton'
import { AttemptHistory } from '@/features/practice/AttemptHistory'
import { formatDateShort, formatDecimal, formatNumber, formatRelativeDays, pluralDays } from '@/lib/format'
import { CARD_STATUS_LABELS } from '@/lib/labels'
import { probeDescription } from '@/lib/levels'
import type { CardDetail } from '@/types/api'

export function CardDetailPage() {
  const { id } = useParams<{ id: string }>()
  const card = useCard(id)
  const suspend = useSuspendCard()
  const unsuspend = useUnsuspendCard()

  if (card.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (card.isError) {
    const notFound = isApiError(card.error) && card.error.status === 404
    return (
      <Alert variant="destructive">
        <AlertTitle>{notFound ? 'Card não encontrado' : 'Não foi possível carregar o card'}</AlertTitle>
        <AlertDescription>
          <Link to="/cards" className="underline">
            Voltar para a lista
          </Link>
        </AlertDescription>
      </Alert>
    )
  }

  const data = card.data
  const suspended = data.status === 'suspended'
  const toggling = suspend.isPending || unsuspend.isPending
  const toggleError = suspend.error ?? unsuspend.error

  return (
    <div className="space-y-6">
      <Link to="/cards" className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg">
        <ArrowLeft className="size-4" aria-hidden="true" /> Cards
      </Link>

      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            {data.category.name}
            {data.category.scope === 'personal' ? <span className="text-level-accent">· pessoal</span> : null}
          </Badge>
          <LevelBadge band={data.cefr_level} probe={data.probe} />
          <MaturityBadge maturity={data.maturity} />
          {data.status !== 'active' ? (
            <Badge variant="warning">{CARD_STATUS_LABELS[data.status]}</Badge>
          ) : null}
        </div>
        {data.scenario ? <p className="italic text-fg-muted">{data.scenario}</p> : null}
        <h1 className="text-display text-2xl leading-snug sm:text-3xl">{data.question_text}</h1>
        {data.probe !== 'none' ? (
          <p className="text-xs text-fg-muted">{probeDescription(data.probe)}</p>
        ) : null}
      </header>

      <div className="grid gap-6 md:grid-cols-[1fr_280px]">
        <div className="space-y-6">
          <SchedulerCard card={data} />

          {data.key_points.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">O que uma resposta completa costuma cobrir</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-sm">
                  {data.key_points.map((point, i) => (
                    <li key={i}>{point}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          <AttemptHistory cardId={data.id} title="Histórico de tentativas" defaultOpen />
        </div>

        <aside className="space-y-4 md:sticky md:top-20 md:self-start">
          {data.last_scores ? (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Última avaliação</CardTitle>
                <p className="text-xs text-fg-muted">{formatDateShort(data.last_scores.attempted_on)}</p>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-2">
                  <ScorePill axis="structure" score={data.last_scores.structure} />
                  <ScorePill axis="grammar" score={data.last_scores.grammar} />
                  <ScorePill axis="fluency" score={data.last_scores.fluency} />
                </div>
                <p className="text-sm text-fg-muted">
                  Composta{' '}
                  <strong className="text-fg tabular">{formatDecimal(data.last_scores.composite, 2)}</strong>
                </p>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardContent className="space-y-3 pt-5">
              <p className="text-sm text-fg-muted">
                {suspended
                  ? 'Card suspenso: não entra na fila até ser reativado.'
                  : 'Suspender tira o card da fila de revisões sem apagar o histórico.'}
              </p>
              {suspended ? (
                <Button className="w-full" onClick={() => unsuspend.mutate(data.id)} loading={toggling}>
                  <Play /> Reativar card
                </Button>
              ) : (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => suspend.mutate(data.id)}
                  loading={toggling}
                >
                  <Pause /> Suspender card
                </Button>
              )}
              {toggleError ? (
                <p className="text-sm text-danger">
                  {toggleError instanceof Error ? toggleError.message : 'Erro.'}
                </p>
              ) : null}
              <dl className="grid grid-cols-2 gap-1 border-t border-border pt-3 text-xs text-fg-muted">
                <dt>Origem</dt>
                <dd className="text-right text-fg">{data.source}</dd>
                <dt>Dificuldade</dt>
                <dd className="text-right text-fg tabular">{formatNumber(data.difficulty_rating)}</dd>
                <dt>Criado em</dt>
                <dd className="text-right text-fg">{formatDateShort(data.created_at)}</dd>
                <dt>Tentativas</dt>
                <dd className="text-right text-fg tabular">{data.attempt_count}</dd>
              </dl>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  )
}

function SchedulerCard({ card }: { card: CardDetail }) {
  const s = card.scheduler
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Agendamento</CardTitle>
      </CardHeader>
      <CardContent>
        {!s ? (
          <p className="text-sm text-fg-muted">Este card ainda não foi respondido — entra como novo.</p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3">
            <Stat
              label="Próxima revisão"
              value={s.due_date ? formatRelativeDays(s.due_date) : '—'}
              hint={s.due_date ? formatDateShort(s.due_date) : 'não agendada'}
            />
            <Stat label="Intervalo" value={s.interval_days > 0 ? pluralDays(s.interval_days) : '—'} />
            <Stat label="Facilidade" value={formatDecimal(s.ease_factor, 2)} />
            <Stat label="Repetições" value={formatNumber(s.repetitions)} />
            <Stat label="Lapsos" value={formatNumber(s.lapses)} />
            <Stat
              label="Última revisão"
              value={s.last_reviewed_on ? formatDateShort(s.last_reviewed_on) : '—'}
              hint={s.last_quality !== null ? `qualidade ${s.last_quality}/5` : undefined}
            />
          </dl>
        )}
      </CardContent>
    </Card>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-fg-muted">{label}</dt>
      <dd className="text-display mt-1 text-2xl tabular">{value}</dd>
      {hint ? <dd className="text-xs text-fg-muted">{hint}</dd> : null}
    </div>
  )
}
