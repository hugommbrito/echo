import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useThinkingTimer } from './useThinkingTimer'

describe('useThinkingTimer', () => {
  let clock = 0
  const now = () => clock

  beforeEach(() => {
    clock = 1000
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts on mount, ticks while live and freezes at the first stop', () => {
    const { result } = renderHook(() => useThinkingTimer({ live: true, now }))
    expect(result.current.running).toBe(true)
    expect(result.current.result).toBeNull()

    clock = 3500
    act(() => {
      vi.advanceTimersByTime(250)
    })
    expect(result.current.elapsed).toBeCloseTo(2.5)

    clock = 5000
    act(() => result.current.stop())
    expect(result.current.running).toBe(false)
    expect(result.current.result).toBeCloseTo(4)

    clock = 9000
    act(() => result.current.stop()) // "Regravar": a second press must not restart
    expect(result.current.result).toBeCloseTo(4)
  })

  it('measures without ticking when the timer is hidden', () => {
    const { result } = renderHook(() => useThinkingTimer({ live: false, now }))
    clock = 4000
    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(result.current.elapsed).toBe(0)
    act(() => result.current.stop())
    expect(result.current.result).toBeCloseTo(3)
  })

  it('restart begins a fresh measurement', () => {
    const { result } = renderHook(() => useThinkingTimer({ now }))
    clock = 2000
    act(() => result.current.stop())
    expect(result.current.result).toBeCloseTo(1)
    clock = 10000
    act(() => result.current.restart())
    expect(result.current.running).toBe(true)
    expect(result.current.result).toBeNull()
    clock = 12000
    act(() => result.current.stop())
    expect(result.current.result).toBeCloseTo(2)
  })

  it('flags the measurement when the tab is hidden while thinking', () => {
    const { result } = renderHook(() => useThinkingTimer({ now }))
    expect(result.current.interrupted).toBe(false)
    const spy = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(result.current.interrupted).toBe(true)
    spy.mockRestore()
  })
})
