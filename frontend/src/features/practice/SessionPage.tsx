import { ArrowRight, Check, PartyPopper, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { useAttempt, useCreateAttempt, useInvalidateAfterAttempt, useRetryAttempt } from '@/api/attempts'
import { useMe } from '@/api/auth'
import { isApiError } from '@/api/client'
import { useRetryGeneration, useSession, useSessionQueue } from '@/api/sessions'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { LanguageTag } from '@/components/ui/LanguageTag'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/cn'
import { formatNumber, formatSigned } from '@/lib/format'
import { findProfile, languageMeta } from '@/lib/languages'
import type { QueueItem, Session, SessionPlan } from '@/types/api'

import { AttemptHistory } from './AttemptHistory'
import { CardPrompt } from './CardPrompt'
import { EvaluationPanel, ReviewSummary } from './EvaluationPanel'
import type { Recording } from './hooks/useAudioRecorder'
import { LevelDelta } from './LevelDelta'
import { ProcessingSteps } from './ProcessingSteps'
import { Recorder } from './Recorder'

export function SessionPage() {
  const { id } = useParams<{ id: string }>()
  const session = useSession(id)
  const retry = useRetryGeneration()

  if (session.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (session.isError) {
    const notFound = isApiError(session.error) && session.error.status === 404
    return (
      <Alert variant="destructive">
        <AlertTitle>{notFound ? 'Sessão não encontrada' : 'Não foi possível carregar a sessão'}</AlertTitle>
        <AlertDescription>
          <Link to="/today" className="underline">
            Voltar para Hoje
          </Link>
        </AlertDescription>
      </Alert>
    )
  }

  const data = session.data

  if (data.status === 'generating') {
    return (
      <div className="flex flex-col items-center gap-4 py-24 text-center">
        <Spinner size="lg" label="Gerando perguntas" />
        <h1 className="text-display text-2xl">Gerando suas perguntas…</h1>
        <p className="max-w-sm text-sm text-fg-muted">{generatingText(data)}</p>
      </div>
    )
  }

  if (data.status === 'failed') {
    return (
      <div className="mx-auto max-w-lg space-y-4 py-12">
        <Alert variant="destructive">
          <AlertTitle>A geração das perguntas falhou</AlertTitle>
          <AlertDescription>{data.generation_error || 'Erro desconhecido.'}</AlertDescription>
        </Alert>
        {retry.isError ? (
          <p className="text-sm text-danger">
            {retry.error instanceof Error ? retry.error.message : 'Erro ao tentar de novo.'}
          </p>
        ) : null}
        <div className="flex gap-2">
          <Button onClick={() => retry.mutate(data.id)} loading={retry.isPending}>
            <RotateCcw /> Tentar gerar de novo
          </Button>
          <Button variant="ghost" asChild>
            <Link to="/today">Voltar</Link>
          </Button>
        </div>
      </div>
    )
  }

  return <SessionRunner session={data} />
}

/** "Preparando 3 perguntas em inglês (A2) e 2 em francês (A1). Isso leva alguns segundos." */
function generatingText(session: Session): string {
  const parts = session.plans
    .filter((plan) => plan.new_cards_target > 0 && plan.generation_status !== 'ready')
    .map(
      (plan) =>
        `${plan.new_cards_target} ${plan.new_cards_target === 1 ? 'pergunta' : 'perguntas'} ${languageMeta(plan.language).inPhrase} (${plan.base_level})`,
    )
  if (parts.length === 0) return 'Isso leva alguns segundos.'
  const list = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(', ')} e ${parts[parts.length - 1]}`
  return `Preparando ${list}. Isso leva alguns segundos.`
}

// ---------------------------------------------------------------------------

function SessionRunner({ session }: { session: Session }) {
  const [run, setRun] = useState(0)
  const [params, setParams] = useSearchParams()
  const requested = params.get('language')
  const language = requested && session.plans.some((p) => p.language === requested) ? requested : null
  const queue = useSessionQueue(session.id, 1, language)
  const { progress } = session
  const total = progress.new_total + progress.due_total
  const done = progress.new_done + progress.due_done
  const item = queue.data?.[0]
  const current = language ? session.plans.find((p) => p.language === language) : null

  const next = () => {
    setRun((r) => r + 1)
    void queue.refetch()
  }

  const selectLanguage = (code: string | null) => {
    setParams(
      (prev) => {
        const nextParams = new URLSearchParams(prev)
        if (code) nextParams.set('language', code)
        else nextParams.delete('language')
        return nextParams
      },
      { replace: true },
    )
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-display text-2xl tabular">
            {done} <span className="text-fg-muted">de {total}</span>
          </h1>
          <p className="text-sm text-fg-muted tabular">
            {current ? (
              <>
                {languageMeta(current.language).label}: novos {current.progress.new_done}/
                {current.progress.new_total} · revisões {current.progress.due_done}/
                {current.progress.due_total}
              </>
            ) : (
              <>
                Novos {progress.new_done}/{progress.new_total} · Revisões {progress.due_done}/
                {progress.due_total}
              </>
            )}
          </p>
        </div>
        <Progress value={total > 0 ? (done / total) * 100 : 100} size="sm" label="Progresso da sessão" />
        {session.plans.length > 1 ? (
          <LanguageFilter plans={session.plans} value={language} onChange={selectLanguage} />
        ) : null}
      </header>

      {queue.isPending ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : queue.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Não foi possível carregar a fila</AlertTitle>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => void queue.refetch()}>
            Tentar de novo
          </Button>
        </Alert>
      ) : !item && language && progress.remaining > 0 ? (
        <LanguageDone language={language} onShowAll={() => selectLanguage(null)} />
      ) : !item ? (
        <Completion session={session} />
      ) : (
        <CardRunner key={`${item.card.id}-${run}`} item={item} sessionId={session.id} onNext={next} />
      )}
    </div>
  )
}

function LanguageFilter({
  plans,
  value,
  onChange,
}: {
  plans: SessionPlan[]
  value: string | null
  onChange: (code: string | null) => void
}) {
  const options: { key: string | null; label: string; done: number; total: number }[] = [
    {
      key: null,
      label: 'Todos',
      done: plans.reduce((s, p) => s + p.progress.new_done + p.progress.due_done, 0),
      total: plans.reduce((s, p) => s + p.progress.new_total + p.progress.due_total, 0),
    },
    ...plans.map((p) => ({
      key: p.language,
      label: languageMeta(p.language).label,
      done: p.progress.new_done + p.progress.due_done,
      total: p.progress.new_total + p.progress.due_total,
    })),
  ]
  return (
    <div
      className="inline-flex flex-wrap rounded-lg border border-border bg-surface p-0.5 text-sm"
      role="radiogroup"
      aria-label="Idioma"
    >
      {options.map((option) => {
        const checked = value === option.key
        return (
          <button
            key={option.key ?? 'all'}
            type="button"
            role="radio"
            aria-checked={checked}
            onClick={() => onChange(option.key)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 tabular',
              checked ? 'bg-bg font-semibold text-fg' : 'text-fg-muted hover:text-fg',
            )}
          >
            {checked ? <Check className="size-4" strokeWidth={3} aria-hidden="true" /> : null}
            {option.key ? <LanguageTag code={option.key} full bare /> : option.label}
            <span className="text-xs text-fg-muted">
              {option.done}/{option.total}
            </span>
          </button>
        )
      })}
    </div>
  )
}

function LanguageDone({ language, onShowAll }: { language: string; onShowAll: () => void }) {
  const meta = languageMeta(language)
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <Check className="size-10 text-success" aria-hidden="true" />
      <h2 className="text-display text-3xl">Você terminou o {meta.label.toLowerCase()} de hoje.</h2>
      <p className="text-fg-muted">Ainda há cards nos outros idiomas.</p>
      <Button size="lg" onClick={onShowAll}>
        Ver os outros idiomas <ArrowRight />
      </Button>
    </div>
  )
}

function Completion({ session }: { session: Session }) {
  const { progress } = session
  const me = useMe()
  return (
    <div className="flex flex-col items-center gap-5 py-16 text-center">
      <PartyPopper className="size-12 text-level-accent" aria-hidden="true" />
      <h2 className="text-display text-4xl">Sessão concluída!</h2>
      <p className="text-fg-muted tabular">
        {progress.new_done} {progress.new_done === 1 ? 'pergunta nova' : 'perguntas novas'} ·{' '}
        {progress.due_done} {progress.due_done === 1 ? 'revisão' : 'revisões'}
      </p>
      {session.plans.length > 0 ? (
        <ul className="space-y-1 text-sm text-fg-muted tabular" aria-label="Por idioma">
          {session.plans.map((plan) => {
            const profile = findProfile(me.data, plan.language)
            const delta = profile ? profile.level.rating - plan.rating_at_start : null
            return (
              <li key={plan.language} className="flex flex-wrap items-center justify-center gap-x-2">
                <LanguageTag code={plan.language} full bare />
                <span>
                  {plan.progress.new_done} {plan.progress.new_done === 1 ? 'nova' : 'novas'} ·{' '}
                  {plan.progress.due_done} {plan.progress.due_done === 1 ? 'revisão' : 'revisões'}
                </span>
                {profile ? (
                  <span>
                    · nível {formatNumber(profile.level.rating)} · {profile.level.band}
                    {delta ? ` (${formatSigned(delta)})` : ''}
                  </span>
                ) : null}
              </li>
            )
          })}
        </ul>
      ) : null}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button asChild size="lg">
          <Link to="/stats">
            Ver estatísticas <ArrowRight />
          </Link>
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link to="/today">Voltar para Hoje</Link>
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------

function CardRunner({ item, sessionId, onNext }: { item: QueueItem; sessionId: string; onNext: () => void }) {
  const [attemptId, setAttemptId] = useState<string | null>(null)
  const create = useCreateAttempt()
  const retry = useRetryAttempt()
  const attemptQuery = useAttempt(attemptId ?? undefined)
  const invalidate = useInvalidateAfterAttempt()
  const invalidatedFor = useRef<string | null>(null)

  const attempt = attemptQuery.data
  const phase: 'record' | 'processing' | 'result' = !attemptId
    ? 'record'
    : attempt?.status === 'completed'
      ? 'result'
      : 'processing'

  useEffect(() => {
    if (attempt?.status === 'completed' && invalidatedFor.current !== attempt.id) {
      invalidatedFor.current = attempt.id
      invalidate(attempt)
    }
  }, [attempt, invalidate])

  const submit = (recording: Recording) => {
    create.mutate(
      {
        cardId: item.card.id,
        sessionId,
        audio: recording.blob,
        durationSeconds: recording.durationSeconds,
        mimeType: recording.mimeType,
        extension: recording.extension,
      },
      { onSuccess: (accepted) => setAttemptId(accepted.id) },
    )
  }

  const rerecord = () => {
    setAttemptId(null)
    create.reset()
    retry.reset()
  }

  const submitError = create.isError
    ? isApiError(create.error)
      ? create.error.code === 'card_suspended'
        ? 'Este card está suspenso e não aceita novas tentativas.'
        : (create.error.fieldError('audio') ??
          create.error.fieldError('duration_seconds') ??
          create.error.detail)
      : 'Falha ao enviar o áudio. Verifique sua conexão e tente de novo.'
    : null

  if (phase === 'record') {
    return (
      <div className="space-y-6">
        <CardPrompt card={item.card} kind={item.kind} origin={item.origin} dueDate={item.due_date} />
        <Recorder
          onSubmit={submit}
          submitting={create.isPending}
          submitError={submitError}
          language={item.card.language}
        />
        <AttemptHistory cardId={item.card.id} />
      </div>
    )
  }

  if (phase === 'processing') {
    return (
      <div className="space-y-6">
        <CardPrompt card={item.card} kind={item.kind} origin={item.origin} dueDate={item.due_date} compact />
        <ProcessingSteps
          attempt={attempt}
          onRetry={() => attemptId && retry.mutate(attemptId)}
          onRerecord={rerecord}
          retrying={retry.isPending}
          retryError={retry.isError ? (retry.error instanceof Error ? retry.error.message : 'Erro.') : null}
        />
        {attemptQuery.isError ? (
          <Alert variant="destructive">
            <AlertDescription>
              Perdemos a conexão com o processamento. Estamos tentando de novo…
            </AlertDescription>
          </Alert>
        ) : null}
      </div>
    )
  }

  // phase === 'result'
  if (!attempt) return null
  return (
    <div className="space-y-6">
      <CardPrompt card={item.card} kind={item.kind} origin={item.origin} dueDate={item.due_date} compact />
      <EvaluationPanel attempt={attempt} />
      {attempt.review && !attempt.insufficient_speech ? <ReviewSummary review={attempt.review} /> : null}
      <LevelDelta attempt={attempt} card={item.card} />
      <AttemptHistory cardId={item.card.id} excludeAttemptId={attempt.id} />
      <div className="sticky bottom-16 z-10 flex flex-col-reverse gap-2 rounded-2xl border border-border bg-bg/95 p-3 backdrop-blur sm:bottom-4 sm:flex-row sm:justify-end">
        <Button variant="outline" size="lg" onClick={rerecord}>
          <RotateCcw /> {attempt.insufficient_speech ? 'Gravar de novo' : 'Tentar de novo'}
        </Button>
        <Button size="lg" onClick={onNext}>
          Próximo <ArrowRight />
        </Button>
      </div>
    </div>
  )
}
