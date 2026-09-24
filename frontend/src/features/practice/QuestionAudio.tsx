import { Square, Volume2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'
import { formatSeconds } from '@/lib/format'

import type { QuestionAudioApi } from './hooks/useQuestionAudio'

export interface QuestionAudioProps {
  audio: QuestionAudioApi
  /** Listen-only mode: the button is the main call to action. */
  emphasis?: boolean
  /** While the microphone is open, so the voice does not land in the recording. */
  disabled?: boolean
  durationSeconds?: number | null
}

/** "Ouvir pergunta" button + 0,8× toggle + play count. Never autoplays. */
export function QuestionAudio({
  audio,
  emphasis = false,
  disabled = false,
  durationSeconds,
}: QuestionAudioProps) {
  const playing = audio.status === 'playing'
  const loading = audio.status === 'loading'
  const label = playing ? 'Parar áudio' : 'Ouvir pergunta'
  return (
    <div className="flex flex-wrap items-center gap-3" aria-label="Áudio da pergunta">
      <Button
        type="button"
        variant={emphasis ? 'default' : 'outline'}
        size={emphasis ? 'lg' : 'md'}
        onClick={() => (playing ? audio.pause() : audio.play())}
        disabled={disabled || !audio.available}
        loading={loading}
        aria-label={label}
      >
        {playing ? <Square className="fill-current" /> : <Volume2 />}
        {label}
      </Button>
      <button
        type="button"
        role="switch"
        aria-checked={audio.rate === 0.8}
        aria-label="Velocidade reduzida (0,8×)"
        onClick={audio.toggleRate}
        disabled={!audio.available}
        className={cn(
          'rounded-full border px-2.5 py-1 text-xs tabular transition-colors disabled:opacity-50',
          audio.rate === 0.8
            ? 'border-primary bg-primary text-primary-fg'
            : 'border-border bg-surface text-fg-muted hover:text-fg',
        )}
      >
        0,8×
      </button>
      <span className="text-xs text-fg-muted tabular">
        {durationSeconds ? formatSeconds(durationSeconds) : null}
        {durationSeconds && audio.plays > 0 ? ' · ' : null}
        {audio.plays > 0 ? `ouviu ${audio.plays}×` : null}
      </span>
      {audio.status === 'error' && audio.error ? (
        <p role="alert" className="basis-full text-xs text-danger">
          {audio.error}
        </p>
      ) : null}
    </div>
  )
}
