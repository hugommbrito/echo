import { useCallback, useEffect, useRef, useState } from 'react'

export interface ThinkingTimerOptions {
  /** Tick `elapsed` every 250 ms for a visible timer. Off, the hook only measures on `stop()`. */
  live?: boolean
  /** Clock in milliseconds (injectable for tests). */
  now?: () => number
}

export interface ThinkingTimerApi {
  /** Live seconds since the question was shown (only updated while `running && live`). */
  elapsed: number
  running: boolean
  /** Seconds from show to the first `stop()`; null while running. */
  result: number | null
  /** The tab was hidden while thinking: the measurement is unreliable, send nothing. */
  interrupted: boolean
  /** Idempotent: the first call freezes `result`. */
  stop: () => void
  /** Fresh measurement from now (not used by "Regravar", which keeps the first press). */
  restart: () => void
}

const defaultNow = () => performance.now()

/**
 * Starts when the component mounts (= the question is displayed) and stops at the first press on
 * "record". Mount/unmount follows `CardRunner`'s key, so "Próximo" starts a new measurement.
 */
export function useThinkingTimer({
  live = true,
  now = defaultNow,
}: ThinkingTimerOptions = {}): ThinkingTimerApi {
  const nowRef = useRef(now)
  useEffect(() => {
    nowRef.current = now
  }, [now])
  const [startedAt, setStartedAt] = useState(() => now())
  const [result, setResult] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [interrupted, setInterrupted] = useState(false)
  const running = result === null

  useEffect(() => {
    if (!running || !live) return
    const tick = () => setElapsed(Math.max(0, (nowRef.current() - startedAt) / 1000))
    tick()
    const id = window.setInterval(tick, 250)
    return () => window.clearInterval(id)
  }, [running, live, startedAt])

  useEffect(() => {
    if (!running || typeof document === 'undefined') return
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') setInterrupted(true)
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [running])

  const stop = useCallback(() => {
    setResult((current) => current ?? Math.max(0, (nowRef.current() - startedAt) / 1000))
  }, [startedAt])

  const restart = useCallback(() => {
    setStartedAt(nowRef.current())
    setResult(null)
    setElapsed(0)
    setInterrupted(false)
  }, [])

  return { elapsed, running, result, interrupted, stop, restart }
}
