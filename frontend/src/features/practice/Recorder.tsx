import { Mic, RotateCcw, Send, Square } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/cn'
import { formatDuration } from '@/lib/format'
import { languageMeta } from '@/lib/languages'

import {
  MAX_SECONDS,
  MIN_SECONDS,
  useAudioRecorder,
  type Recording,
  type RecorderStatus,
} from './hooks/useAudioRecorder'

export interface RecorderProps {
  onSubmit: (recording: Recording) => void
  submitting?: boolean
  submitError?: string | null
  disabled?: boolean
  /** Card language → "Responda em francês" above the button. */
  language?: string
  /** Fired on every status change; `requesting` is the press on the record button. */
  onStatusChange?: (status: RecorderStatus) => void
}

export function Recorder({
  onSubmit,
  submitting = false,
  submitError,
  disabled = false,
  language,
  onStatusChange,
}: RecorderProps) {
  const rec = useAudioRecorder()
  const onStatusChangeRef = useRef(onStatusChange)
  useEffect(() => {
    onStatusChangeRef.current = onStatusChange
  }, [onStatusChange])
  useEffect(() => {
    onStatusChangeRef.current?.(rec.status)
  }, [rec.status])
  const isRecording = rec.status === 'recording'
  const isRequesting = rec.status === 'requesting'
  const hasRecording = rec.status === 'stopped' && rec.recording !== null
  const tooShort = hasRecording && (rec.recording?.durationSeconds ?? 0) < MIN_SECONDS
  const pct = (rec.elapsed / MAX_SECONDS) * 100
  const nearLimit = isRecording && rec.elapsed >= MAX_SECONDS - 30

  return (
    <section aria-label="Gravador" className="rounded-2xl border border-border bg-surface p-5 sm:p-6">
      <div className="flex flex-col items-center gap-4">
        {language ? (
          <p className="inline-flex items-center gap-2 text-sm font-medium">
            <span
              aria-hidden="true"
              className="size-2 rounded-full"
              style={{ backgroundColor: `var(${languageMeta(language).colorVar})` }}
            />
            Responda {languageMeta(language).inPhrase}
          </p>
        ) : null}
        {!hasRecording ? (
          <button
            type="button"
            onClick={() => (isRecording ? rec.stop() : void rec.start())}
            disabled={disabled || isRequesting || submitting}
            aria-label={isRecording ? 'Parar gravação' : 'Gravar resposta'}
            aria-pressed={isRecording}
            className={cn(
              'grid size-24 place-items-center rounded-full text-white shadow-lg transition-transform active:scale-95',
              'focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/50',
              'disabled:cursor-not-allowed disabled:opacity-50',
              isRecording ? 'bg-danger animate-pulse' : 'bg-primary text-primary-fg',
            )}
          >
            {isRecording ? (
              <Square className="size-8 fill-current" aria-hidden="true" />
            ) : (
              <Mic className="size-9" aria-hidden="true" />
            )}
          </button>
        ) : null}

        <div className="w-full max-w-sm space-y-2 text-center">
          <p
            className={cn('text-display text-5xl tabular', nearLimit && 'text-danger')}
            aria-live={isRecording ? 'off' : 'polite'}
          >
            {formatDuration(hasRecording ? rec.recording?.durationSeconds : rec.elapsed)}
            <span className="ml-1 text-lg text-fg-muted">/ {formatDuration(MAX_SECONDS)}</span>
          </p>
          <Progress
            value={pct}
            size="sm"
            color={nearLimit ? 'var(--danger)' : 'var(--primary)'}
            label="Tempo de gravação"
          />
          <p className="text-xs text-fg-muted">
            {isRecording
              ? 'Gravando… toque para parar.'
              : isRequesting
                ? 'Aguardando permissão do microfone…'
                : hasRecording
                  ? 'Ouça a prévia antes de enviar.'
                  : `Mínimo ${MIN_SECONDS} s · máximo ${formatDuration(MAX_SECONDS)}. Toque para gravar.`}
          </p>
        </div>

        {hasRecording && rec.recording ? (
          <div className="w-full max-w-md space-y-4">
            <audio controls src={rec.recording.url} className="w-full" aria-label="Prévia da gravação" />
            {tooShort ? (
              <Alert variant="warning">
                <AlertDescription>Grave pelo menos {MIN_SECONDS} segundos para enviar.</AlertDescription>
              </Alert>
            ) : null}
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-center">
              <Button variant="outline" size="lg" onClick={rec.reset} disabled={submitting}>
                <RotateCcw /> Regravar
              </Button>
              <Button
                size="lg"
                onClick={() => rec.recording && onSubmit(rec.recording)}
                disabled={tooShort || disabled}
                loading={submitting}
              >
                <Send /> Enviar
              </Button>
            </div>
          </div>
        ) : null}

        {rec.error ? (
          <Alert variant="destructive" className="max-w-md">
            <AlertDescription>{rec.error}</AlertDescription>
          </Alert>
        ) : null}
        {submitError ? (
          <Alert variant="destructive" className="max-w-md">
            <AlertDescription>{submitError}</AlertDescription>
          </Alert>
        ) : null}
      </div>
    </section>
  )
}
