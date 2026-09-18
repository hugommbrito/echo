import { describe, expect, it, vi } from 'vitest'

import { MIME_CANDIDATES, extensionForMime, pickMimeType, startRecorder } from './useAudioRecorder'

describe('pickMimeType', () => {
  it('prefers webm/opus, then mp4, then ogg/opus', () => {
    expect(pickMimeType(() => true)).toBe('audio/webm;codecs=opus')
    expect(pickMimeType((t) => t === 'audio/mp4')).toBe('audio/mp4')
    expect(pickMimeType((t) => t.startsWith('audio/ogg'))).toBe('audio/ogg;codecs=opus')
  })

  it('returns null when nothing is supported', () => {
    expect(pickMimeType(() => false)).toBeNull()
  })

  it('treats a throwing isTypeSupported as unsupported and keeps going', () => {
    const isSupported = (t: string) => {
      if (t === MIME_CANDIDATES[0]) throw new Error('boom')
      return t === 'audio/mp4'
    }
    expect(pickMimeType(isSupported)).toBe('audio/mp4')
  })

  it('respects a custom candidate list', () => {
    expect(pickMimeType(() => true, ['audio/ogg;codecs=opus', 'audio/webm'])).toBe('audio/ogg;codecs=opus')
  })
})

describe('extensionForMime', () => {
  it('maps containers to upload extensions', () => {
    expect(extensionForMime('audio/webm;codecs=opus')).toBe('webm')
    expect(extensionForMime('audio/mp4')).toBe('mp4')
    expect(extensionForMime('audio/ogg;codecs=opus')).toBe('ogg')
    expect(extensionForMime('audio/wav')).toBe('wav')
    expect(extensionForMime('')).toBe('bin')
    expect(extensionForMime(null)).toBe('bin')
  })
})

describe('startRecorder', () => {
  it('falls back to the next type when start() throws (iOS quirk)', () => {
    const started: string[] = []
    class FakeRecorder {
      mimeType: string
      constructor(_stream: MediaStream, options?: { mimeType?: string }) {
        this.mimeType = options?.mimeType ?? 'default'
      }
      start() {
        if (this.mimeType === 'audio/webm;codecs=opus') throw new Error('NotSupportedError')
        started.push(this.mimeType)
      }
    }
    vi.stubGlobal('MediaRecorder', FakeRecorder)
    try {
      const recorder = startRecorder({} as MediaStream, MIME_CANDIDATES, () => true)
      expect(recorder.mimeType).toBe('audio/mp4')
      expect(started).toEqual(['audio/mp4'])
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('uses the browser default when no candidate is supported', () => {
    class FakeRecorder {
      mimeType: string
      constructor(_stream: MediaStream, options?: { mimeType?: string }) {
        this.mimeType = options?.mimeType ?? 'browser-default'
      }
      start() {}
    }
    vi.stubGlobal('MediaRecorder', FakeRecorder)
    try {
      const recorder = startRecorder({} as MediaStream, MIME_CANDIDATES, () => false)
      expect(recorder.mimeType).toBe('browser-default')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
