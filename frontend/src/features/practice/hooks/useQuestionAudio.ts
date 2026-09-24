import { useCallback, useEffect, useRef, useState } from 'react'

export type QuestionAudioStatus = 'idle' | 'loading' | 'playing' | 'error'
export type PlaybackRate = 1 | 0.8

export const AUDIO_ERROR_MESSAGE = 'Não foi possível carregar o áudio da pergunta.'

export interface QuestionAudioOptions {
  /** Signed URL from the card payload, or the on-demand endpoint when the card has no audio yet. */
  src: string | null
  /** Always-fresh URL used once when `src` fails (expired signature, missing file). */
  fallbackSrc: string | null
  /** Create/preload the element only while the question is on screen in a mode with audio. */
  enabled: boolean
}

export interface QuestionAudioApi {
  status: QuestionAudioStatus
  /** Playbacks that actually started (the first listen counts as 1). */
  plays: number
  rate: PlaybackRate
  error: string | null
  available: boolean
  /** Restarts from the beginning. Call synchronously from a click handler (iOS needs the gesture). */
  play: () => void
  pause: () => void
  toggleRate: () => void
  /** New attempt on the same card: forget the play count. */
  reset: () => void
}

type MediaWithPitch = HTMLAudioElement & { preservesPitch?: boolean }

function isThenable(value: unknown): value is Promise<unknown> {
  return typeof (value as { then?: unknown } | null)?.then === 'function'
}

/**
 * One `Audio()` per card, preloaded on display so the first tap is instant. Never autoplays.
 * Counts plays, exposes a 0,8× toggle (pitch preserved) and swaps to `fallbackSrc` once on error.
 */
export function useQuestionAudio({ src, fallbackSrc, enabled }: QuestionAudioOptions): QuestionAudioApi {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const fallbackRef = useRef(fallbackSrc)
  useEffect(() => {
    fallbackRef.current = fallbackSrc
  }, [fallbackSrc])
  const usingFallbackRef = useRef(false)
  const wantedRef = useRef(false) // the learner pressed play and it has not started yet
  const countedRef = useRef(false)
  const rateRef = useRef<PlaybackRate>(1)
  const [status, setStatus] = useState<QuestionAudioStatus>('idle')
  const [plays, setPlays] = useState(0)
  const [rate, setRate] = useState<PlaybackRate>(1)
  const [error, setError] = useState<string | null>(null)
  const available = enabled && Boolean(src)

  const fail = useCallback(() => {
    wantedRef.current = false
    setStatus('error')
    setError(AUDIO_ERROR_MESSAGE)
  }, [])

  const swapToFallback = useCallback((audio: HTMLAudioElement): boolean => {
    const fallback = fallbackRef.current
    if (usingFallbackRef.current || !fallback || fallback === audio.getAttribute('src')) return false
    usingFallbackRef.current = true
    audio.src = fallback
    audio.load()
    return true
  }, [])

  const startPlayback = useCallback(
    (audio: HTMLAudioElement) => {
      audio.playbackRate = rateRef.current
      function attempt(mayRetry: boolean) {
        const result = audio.play()
        if (!isThenable(result)) return
        result.catch((err: unknown) => {
          const name = (err as { name?: string } | null)?.name
          if (name === 'AbortError') return // pause() raced play(); nothing to report
          if (name === 'NotAllowedError') {
            wantedRef.current = false
            setStatus('idle') // needs another tap; not an error worth showing
            return
          }
          if (mayRetry && swapToFallback(audio)) {
            attempt(false)
            return
          }
          fail()
        })
      }
      attempt(true)
    },
    [fail, swapToFallback],
  )

  useEffect(() => {
    if (!enabled || !src) return
    const audio = new Audio()
    audio.preload = 'auto'
    try {
      ;(audio as MediaWithPitch).preservesPitch = true
    } catch {
      // older engines
    }
    usingFallbackRef.current = false
    wantedRef.current = false
    countedRef.current = false
    audioRef.current = audio

    const onPlaying = () => {
      setStatus('playing')
      if (wantedRef.current && !countedRef.current) {
        countedRef.current = true
        setPlays((n) => n + 1)
      }
      wantedRef.current = false
    }
    const onWaiting = () => setStatus('loading')
    const onStop = () => setStatus('idle')
    const onError = () => {
      const wanted = wantedRef.current
      if (swapToFallback(audio)) {
        if (wanted) startPlayback(audio)
        return
      }
      if (wanted) fail()
      else setStatus('idle') // a failed preload is not an error until she asks to listen
    }
    audio.addEventListener('playing', onPlaying)
    audio.addEventListener('waiting', onWaiting)
    audio.addEventListener('pause', onStop)
    audio.addEventListener('ended', onStop)
    audio.addEventListener('error', onError)
    audio.src = src
    audio.load()

    return () => {
      audio.removeEventListener('playing', onPlaying)
      audio.removeEventListener('waiting', onWaiting)
      audio.removeEventListener('pause', onStop)
      audio.removeEventListener('ended', onStop)
      audio.removeEventListener('error', onError)
      audio.pause()
      audio.removeAttribute('src')
      audio.load() // releases the decoder (matters on iOS)
      audioRef.current = null
    }
  }, [enabled, src, fail, startPlayback, swapToFallback])

  const play = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    wantedRef.current = true
    countedRef.current = false
    setError(null)
    setStatus('loading')
    try {
      audio.currentTime = 0
    } catch {
      // not seekable yet
    }
    startPlayback(audio)
  }, [startPlayback])

  const pause = useCallback(() => {
    wantedRef.current = false
    const audio = audioRef.current
    if (!audio) return
    audio.pause()
    setStatus('idle')
  }, [])

  const toggleRate = useCallback(() => {
    const next: PlaybackRate = rateRef.current === 1 ? 0.8 : 1
    rateRef.current = next
    setRate(next)
    if (audioRef.current) audioRef.current.playbackRate = next
  }, [])

  const reset = useCallback(() => {
    pause()
    setPlays(0)
    setError(null)
  }, [pause])

  return { status, plays, rate, error, available, play, pause, toggleRate, reset }
}
