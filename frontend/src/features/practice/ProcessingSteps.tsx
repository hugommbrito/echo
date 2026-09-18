import { Check, Circle, RotateCcw, XCircle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/cn'
import type { Attempt, AttemptStatus } from '@/types/api'

const STEPS: { status: AttemptStatus; label: string }[] = [
  { status: 'uploaded', label: 'Enviado' },
  { status: 'probing', label: 'Verificando áudio' },
  { status: 'transcribing', label: 'Transcrevendo' },
  { status: 'evaluating', label: 'Avaliando' },
  { status: 'scheduling', label: 'Agendando' },
  { status: 'completed', label: 'Concluído' },
]

export interface ProcessingStepsProps {
  attempt: Attempt | undefined
  onRetry: () => void
  onRerecord: () => void
  retrying?: boolean
  retryError?: string | null
}

export function ProcessingSteps({
  attempt,
  onRetry,
  onRerecord,
  retrying = false,
  retryError,
}: ProcessingStepsProps) {
  const status = attempt?.status ?? 'uploaded'
  const failed = status === 'failed'
  const failedStage = failed ? attempt?.failure_stage || 'uploaded' : null
  const currentIndex = failed
    ? Math.max(
        0,
        STEPS.findIndex((s) => s.status === failedStage),
      )
    : STEPS.findIndex((s) => s.status === status)

  return (
    <section
      aria-label="Processamento da tentativa"
      aria-live="polite"
      className="rounded-2xl border border-border bg-surface p-5 sm:p-6"
    >
      <ol className="space-y-3">
        {STEPS.map((step, index) => {
          const done = !failed && (index < currentIndex || status === 'completed')
          const active = !failed && index === currentIndex && status !== 'completed'
          const isFailedStep = failed && index === currentIndex
          return (
            <li
              key={step.status}
              className={cn(
                'flex items-center gap-3 text-sm',
                !done && !active && !isFailedStep && 'text-fg-muted',
              )}
            >
              <span className="grid size-6 place-items-center">
                {isFailedStep ? (
                  <XCircle className="size-5 text-danger" aria-hidden="true" />
                ) : done ? (
                  <Check className="size-5 text-success" aria-hidden="true" />
                ) : active ? (
                  <Spinner size="sm" label={`${step.label}…`} />
                ) : (
                  <Circle className="size-3 opacity-40" aria-hidden="true" />
                )}
              </span>
              <span className={cn(active && 'font-medium', isFailedStep && 'font-medium text-danger')}>
                {step.label}
                {active ? '…' : ''}
              </span>
              {done || active || isFailedStep ? null : <span className="sr-only">(pendente)</span>}
            </li>
          )
        })}
      </ol>

      {failed ? (
        <div className="mt-5 space-y-3">
          <Alert variant="destructive">
            <AlertTitle>Não conseguimos processar sua gravação</AlertTitle>
            <AlertDescription>
              {attempt?.error_message || 'Erro desconhecido durante o processamento.'}
            </AlertDescription>
          </Alert>
          {retryError ? <p className="text-sm text-danger">{retryError}</p> : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" onClick={onRerecord} disabled={retrying}>
              Regravar
            </Button>
            <Button onClick={onRetry} loading={retrying}>
              <RotateCcw /> Tentar processar de novo
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
