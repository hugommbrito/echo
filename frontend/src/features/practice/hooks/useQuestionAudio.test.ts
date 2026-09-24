import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'

import { AUDIO_ERROR_MESSAGE, useQuestionAudio } from './useQuestionAudio'

const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

function rejection(name: string) {
  const error = new Error(name)
  error.name = name
  return Promise.reject(error)
}

describe('useQuestionAudio', () => {
  let play: MockInstance
  let pause: MockInstance
  let load: MockInstance
  const options = {
    src: 'https://storage.example/q.mp3',
    fallbackSrc: '/api/v1/cards/c1/audio/',
    enabled: true,
  }

  beforeEach(() => {
    // jsdom has no media playback: emulate a successful play by firing `playing` asynchronously.
    play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(function (this: HTMLMediaElement) {
      queueMicrotask(() => this.dispatchEvent(new Event('playing')))
      return Promise.resolve()
    })
    pause = vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    load = vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})
  })
  afterEach(() => vi.restoreAllMocks())

  it('creates nothing while disabled', () => {
    const { result } = renderHook(() => useQuestionAudio({ ...options, enabled: false }))
    expect(load).not.toHaveBeenCalled()
    expect(result.current.available).toBe(false)
    act(() => result.current.play())
    expect(play).not.toHaveBeenCalled()
  })

  it('preloads on mount, never autoplays, counts plays and applies the reduced rate', async () => {
    const { result } = renderHook(() => useQuestionAudio(options))
    expect(load).toHaveBeenCalledTimes(1)
    expect(play).not.toHaveBeenCalled()
    expect(result.current.available).toBe(true)
    expect(result.current.plays).toBe(0)

    act(() => result.current.toggleRate())
    expect(result.current.rate).toBe(0.8)

    await act(async () => {
      result.current.play()
      await flush()
    })
    expect(play).toHaveBeenCalledTimes(1)
    expect(result.current.status).toBe('playing')
    expect(result.current.plays).toBe(1)
    const element = play.mock.instances[0] as HTMLMediaElement
    expect(element.playbackRate).toBe(0.8)

    act(() => result.current.pause())
    expect(pause).toHaveBeenCalled()
    expect(result.current.status).toBe('idle')

    await act(async () => {
      result.current.play()
      await flush()
    })
    expect(result.current.plays).toBe(2)

    act(() => result.current.reset())
    expect(result.current.plays).toBe(0)
  })

  it('falls back to the fresh URL once, then reports the error', async () => {
    play.mockImplementation(() => rejection('NotSupportedError'))
    const { result } = renderHook(() => useQuestionAudio(options))
    await act(async () => {
      result.current.play()
      await flush()
      await flush()
    })
    expect(play).toHaveBeenCalledTimes(2) // signed URL, then the on-demand endpoint
    expect(load).toHaveBeenCalledTimes(2) // preload, then the swapped source
    const element = play.mock.instances[0] as HTMLMediaElement
    expect(element.getAttribute('src')).toBe(options.fallbackSrc)
    expect(result.current.status).toBe('error')
    expect(result.current.error).toBe(AUDIO_ERROR_MESSAGE)
    expect(result.current.plays).toBe(0)
  })

  it('treats a blocked play() as "tap again", not as an error', async () => {
    play.mockImplementation(() => rejection('NotAllowedError'))
    const { result } = renderHook(() => useQuestionAudio(options))
    await act(async () => {
      result.current.play()
      await flush()
    })
    expect(result.current.status).toBe('idle')
    expect(result.current.error).toBeNull()
    expect(play).toHaveBeenCalledTimes(1)
  })

  it('releases the element on unmount', () => {
    const { unmount } = renderHook(() => useQuestionAudio(options))
    unmount()
    expect(pause).toHaveBeenCalledTimes(1)
    expect(load).toHaveBeenCalledTimes(2) // preload + release
  })
})
