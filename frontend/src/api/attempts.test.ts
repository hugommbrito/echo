import { describe, expect, it } from 'vitest'

import { buildAttemptFormData, type CreateAttemptInput } from './attempts'

const base: CreateAttemptInput = {
  cardId: 'c1',
  sessionId: 's1',
  audio: new Blob(['x'], { type: 'audio/webm' }),
  durationSeconds: 31.5,
  mimeType: 'audio/webm',
  extension: 'webm',
}

describe('buildAttemptFormData', () => {
  it('keeps the historical fields and omits telemetry that was not measured', () => {
    const form = buildAttemptFormData(base)
    expect(form.get('card_id')).toBe('c1')
    expect(form.get('session_id')).toBe('s1')
    expect(form.get('duration_seconds')).toBe('31.50')
    expect(form.get('mime_type')).toBe('audio/webm')
    expect(form.get('thinking_seconds')).toBeNull()
    expect(form.get('question_mode')).toBeNull()
    expect(form.get('audio_replays')).toBeNull()
    expect(form.get('text_revealed')).toBeNull()
  })

  it('appends the thinking time and the presentation telemetry', () => {
    const form = buildAttemptFormData({
      ...base,
      thinkingSeconds: 7.5,
      questionMode: 'listen',
      audioReplays: 2,
      textRevealed: true,
    })
    expect(form.get('thinking_seconds')).toBe('7.50')
    expect(form.get('question_mode')).toBe('listen')
    expect(form.get('audio_replays')).toBe('2')
    expect(form.get('text_revealed')).toBe('true')
  })

  it('sends nothing for a retake and clamps odd values', () => {
    const retake = buildAttemptFormData({
      ...base,
      thinkingSeconds: null,
      textRevealed: false,
      audioReplays: 0,
    })
    expect(retake.get('thinking_seconds')).toBeNull()
    expect(retake.get('text_revealed')).toBe('false')
    expect(retake.get('audio_replays')).toBe('0')

    const odd = buildAttemptFormData({ ...base, thinkingSeconds: 99999, audioReplays: 2.7 })
    expect(odd.get('thinking_seconds')).toBe('9999.99')
    expect(odd.get('audio_replays')).toBe('2')
    expect(buildAttemptFormData({ ...base, thinkingSeconds: -3 }).get('thinking_seconds')).toBe('0.00')
    expect(buildAttemptFormData({ ...base, thinkingSeconds: Number.NaN }).get('thinking_seconds')).toBeNull()
  })
})
