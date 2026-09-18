import { useCallback, useEffect, useRef, useState } from 'react'

/** Preferred container/codec order (see plan 14.3). */
export const MIME_CANDIDATES: readonly string[] = [
  'audio/webm;codecs=opus',
  'audio/mp4',
  'audio/ogg;codecs=opus',
]

export const MAX_SECONDS = 300
export const MIN_SECONDS = 3

/** First candidate the browser claims to support, or `null`. Pure: pass `MediaRecorder.isTypeSupported`. */
export function pickMimeType(
  isSupported: (type: string) => boolean,
  candidates: readonly string[] = MIME_CANDIDATES,
): string | null {
  for (const candidate of candidates) {
    try {
      if (isSupported(candidate)) return candidate
    } catch {
      // some engines throw on unknown types; treat as unsupported
    }
  }
  return null
}

/** File extension for the upload name (`recording.<ext>`). */
export function extensionForMime(mime: string | null | undefined): string {
  const base = (mime ?? '').split(';')[0].trim().toLowerCase()
  switch (base) {
    case 'audio/webm':
    case 'video/webm':
      return 'webm'
    case 'audio/mp4':
    case 'audio/x-m4a':
    case 'audio/m4a':
    case 'audio/aac':
      return 'mp4'
    case 'audio/ogg':
    case 'audio/oga':
      return 'ogg'
    case 'audio/wav':
    case 'audio/x-wav':
    case 'audio/wave':
      return 'wav'
    case 'audio/mpeg':
    case 'audio/mp3':
      return 'mp3'
    default:
      return 'bin'
  }
}

/**
 * Build and start a MediaRecorder, trying each supported mime type in order.
 * `start()` is wrapped because iOS may claim support and still fail.
 * Falls back to the browser default when every candidate fails.
 */
export function startRecorder(
  stream: MediaStream,
  candidates: readonly string[] = MIME_CANDIDATES,
  isSupported: (type: string) => boolean = (type) =>
    typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type),
): MediaRecorder {
  const supported = candidates.filter((c) => {
    try {
      return isSupported(c)
    } catch {
      return false
    }
  })
  let lastError: unknown
  for (const mimeType of supported) {
    try {
      const recorder = new MediaRecorder(stream, { mimeType })
      recorder.start()
      return recorder
    } catch (error) {
      lastError = error
    }
  }
  try {
    const recorder = new MediaRecorder(stream)
    recorder.start()
    return recorder
  } catch (error) {
    throw lastError ?? error
  }
}

export type RecorderStatus = 'idle' | 'requesting' | 'recording' | 'stopped'

export interface Recording {
  blob: Blob
  url: string
  mimeType: string
  extension: string
  durationSeconds: number
}

export interface AudioRecorderState {
  status: RecorderStatus
  /** Seconds elapsed while recording (live). */
  elapsed: number
  recording: Recording | null
  error: string | null
  supported: boolean
}

export interface AudioRecorderApi extends AudioRecorderState {
  start: () => Promise<void>
  stop: () => void
  reset: () => void
}

function describeError(error: unknown): string {
  const name = error instanceof DOMException ? error.name : (error as { name?: string } | null)?.name
  switch (name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
    case 'SecurityError':
      return 'Permissão do microfone negada. Libere o acesso nas configurações do navegador e tente de novo.'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'Nenhum microfone encontrado.'
    case 'NotReadableError':
    case 'TrackStartError':
      return 'Não foi possível acessar o microfone. Ele pode estar em uso por outro aplicativo.'
    case 'NotSupportedError':
      return 'Seu navegador não suporta gravação de áudio neste formato.'
    default:
      return 'Não foi possível iniciar a gravação.'
  }
}

export function isRecordingSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.mediaDevices?.getUserMedia === 'function' &&
    typeof MediaRecorder !== 'undefined'
  )
}

/**
 * One-shot recorder: requests the microphone only on `start()`, stops
 * automatically at MAX_SECONDS, releases tracks on stop and exposes a preview URL.
 */
export function useAudioRecorder(): AudioRecorderApi {
  const [status, setStatus] = useState<RecorderStatus>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [recording, setRecording] = useState<Recording | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef(0)
  const tickRef = useRef<number | null>(null)
  const urlRef = useRef<string | null>(null)

  const clearTick = () => {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current)
      tickRef.current = null
    }
  }

  const releaseStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }

  const revokeUrl = () => {
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
  }

  const stop = useCallback(() => {
    const recorder = recorderRef.current
    clearTick()
    if (recorder && recorder.state !== 'inactive') {
      try {
        recorder.stop()
      } catch {
        releaseStream()
        setStatus('idle')
      }
    } else {
      releaseStream()
    }
  }, [])

  const reset = useCallback(() => {
    clearTick()
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.ondataavailable = null
      recorderRef.current.onstop = null
      try {
        recorderRef.current.stop()
      } catch {
        // ignore
      }
    }
    recorderRef.current = null
    releaseStream()
    revokeUrl()
    chunksRef.current = []
    setRecording(null)
    setElapsed(0)
    setError(null)
    setStatus('idle')
  }, [])

  const start = useCallback(async () => {
    if (status === 'recording' || status === 'requesting') return
    if (!isRecordingSupported()) {
      setError('Seu navegador não suporta gravação de áudio. Use Chrome, Edge, Firefox ou Safari atualizado.')
      return
    }
    reset()
    setStatus('requesting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      })
      streamRef.current = stream
      const recorder = startRecorder(stream)
      recorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onerror = () => {
        setError('A gravação foi interrompida pelo navegador.')
        clearTick()
        releaseStream()
        setStatus('idle')
      }
      recorder.onstop = () => {
        const durationSeconds = Math.min(MAX_SECONDS, (performance.now() - startedAtRef.current) / 1000)
        const mimeType = recorder.mimeType || chunksRef.current[0]?.type || 'application/octet-stream'
        const blob = new Blob(chunksRef.current, { type: mimeType })
        releaseStream()
        revokeUrl()
        const url = URL.createObjectURL(blob)
        urlRef.current = url
        setRecording({ blob, url, mimeType, extension: extensionForMime(mimeType), durationSeconds })
        setElapsed(durationSeconds)
        setStatus('stopped')
      }

      startedAtRef.current = performance.now()
      setElapsed(0)
      setStatus('recording')
      tickRef.current = window.setInterval(() => {
        const seconds = (performance.now() - startedAtRef.current) / 1000
        setElapsed(Math.min(MAX_SECONDS, seconds))
        if (seconds >= MAX_SECONDS) stop()
      }, 200)
    } catch (err) {
      releaseStream()
      setError(describeError(err))
      setStatus('idle')
    }
  }, [reset, status, stop])

  // Cleanup on unmount: stop tracks and free the preview URL.
  useEffect(() => {
    return () => {
      clearTick()
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.onstop = null
        try {
          recorderRef.current.stop()
        } catch {
          // ignore
        }
      }
      streamRef.current?.getTracks().forEach((track) => track.stop())
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    }
  }, [])

  return { status, elapsed, recording, error, supported: isRecordingSupported(), start, stop, reset }
}
