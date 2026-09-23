import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, buildQuery, readCookie, request, resetCsrfToken } from './client'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

function lastRequest(fetchMock: ReturnType<typeof vi.fn>, call = 0): { url: string; init: RequestInit } {
  const [url, init] = fetchMock.mock.calls[call] as [string, RequestInit]
  return { url, init }
}

function headerOf(init: RequestInit, name: string): string | undefined {
  const headers = init.headers as Record<string, string>
  return headers[name]
}

describe('readCookie', () => {
  it('reads a named cookie from a cookie string', () => {
    expect(readCookie('csrftoken', 'a=1; csrftoken=abc123; b=2')).toBe('abc123')
    expect(readCookie('missing', 'a=1')).toBeNull()
    expect(readCookie('x', '')).toBeNull()
  })
})

describe('buildQuery', () => {
  it('serialises scalars, joins arrays with commas and drops empties', () => {
    expect(
      buildQuery({ new_cards_target: 3, category_ids: ['a', 'b'], q: '', page: undefined, x: null }),
    ).toBe('?new_cards_target=3&category_ids=a%2Cb')
    expect(buildQuery()).toBe('')
    expect(buildQuery({ category_ids: [] })).toBe('')
    // per-language session targets travel as `lang:count` pairs joined by commas
    expect(buildQuery({ targets: ['en:3', 'fr:2'] })).toBe('?targets=en%3A3%2Cfr%3A2')
  })
})

describe('request / CSRF behaviour', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    resetCsrfToken()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    // clear cookies (jsdom)
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('does not send X-CSRFToken on GET and uses same-origin credentials + JSON accept', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: '1' }))
    const result = await api.get<{ id: string }>('/me/')
    expect(result).toEqual({ id: '1' })
    const { url, init } = lastRequest(fetchMock)
    expect(url).toBe('/api/v1/me/')
    expect(init.method).toBe('GET')
    expect(init.credentials).toBe('same-origin')
    expect(headerOf(init, 'Accept')).toBe('application/json')
    expect(headerOf(init, 'X-CSRFToken')).toBeUndefined()
  })

  it('sends X-CSRFToken from the csrftoken cookie on POST with a JSON body', async () => {
    document.cookie = 'csrftoken=cookie-token; path=/'
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: true }))

    await api.post('/auth/login/', { email: 'a@b.c', password: 'x' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const { init } = lastRequest(fetchMock)
    expect(init.method).toBe('POST')
    expect(headerOf(init, 'X-CSRFToken')).toBe('cookie-token')
    expect(headerOf(init, 'Content-Type')).toBe('application/json')
    expect(init.body).toBe(JSON.stringify({ email: 'a@b.c', password: 'x' }))
  })

  it('falls back to GET /auth/csrf/ once when there is no cookie, and caches the token', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'fetched-token' })) // csrf
      .mockResolvedValueOnce(jsonResponse({ id: 'x' })) // first POST
      .mockResolvedValueOnce(jsonResponse({ id: 'y' })) // second POST

    await api.post('/sessions/', { category_ids: [], new_cards_target: 3 })
    await api.patch('/me/', { timezone: 'America/Toronto' })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(lastRequest(fetchMock, 0).url).toBe('/api/v1/auth/csrf/')
    expect(headerOf(lastRequest(fetchMock, 1).init, 'X-CSRFToken')).toBe('fetched-token')
    expect(headerOf(lastRequest(fetchMock, 2).init, 'X-CSRFToken')).toBe('fetched-token')
    expect(lastRequest(fetchMock, 2).init.method).toBe('PATCH')
  })

  it('sends multipart without a manual Content-Type when the body is FormData', async () => {
    document.cookie = 'csrftoken=cookie-token; path=/'
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'att', status: 'uploaded' }, { status: 202 }))
    const form = new FormData()
    form.append('card_id', 'c1')
    form.append('audio', new Blob(['abc'], { type: 'audio/webm' }), 'recording.webm')

    const result = await api.post<{ id: string; status: string }>('/attempts/', form)

    expect(result.status).toBe('uploaded')
    const { init } = lastRequest(fetchMock)
    expect(init.body).toBe(form)
    expect(headerOf(init, 'Content-Type')).toBeUndefined()
    expect(headerOf(init, 'X-CSRFToken')).toBe('cookie-token')
  })

  it('resolves undefined on 204', async () => {
    document.cookie = 'csrftoken=t; path=/'
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await expect(api.post('/auth/logout/')).resolves.toBeUndefined()
  })

  it('throws ApiError with status/code/detail/errors on non-2xx', async () => {
    document.cookie = 'csrftoken=t; path=/'
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        {
          detail: 'Validation error.',
          code: 'validation_error',
          errors: { new_cards_target: ['Must be ≤ 20.'] },
        },
        { status: 400 },
      ),
    )
    let caught: unknown
    try {
      await request('/sessions/', { method: 'POST', body: {} })
    } catch (error) {
      caught = error
    }
    expect(caught).toBeInstanceOf(ApiError)
    const apiError = caught as ApiError
    expect(apiError.status).toBe(400)
    expect(apiError.code).toBe('validation_error')
    expect(apiError.detail).toBe('Validation error.')
    expect(apiError.errors).toEqual({ new_cards_target: ['Must be ≤ 20.'] })
    expect(apiError.fieldError('new_cards_target')).toBe('Must be ≤ 20.')
    expect(apiError.fieldError('other')).toBeUndefined()
  })

  it('exposes conflict extras such as session_id', async () => {
    document.cookie = 'csrftoken=t; path=/'
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { detail: 'A session already exists for today.', code: 'session_exists', session_id: 's-1' },
        { status: 409 },
      ),
    )
    let caught: unknown
    try {
      await api.post('/sessions/', {})
    } catch (error) {
      caught = error
    }
    expect(caught).toBeInstanceOf(ApiError)
    const apiError = caught as ApiError
    expect(apiError.status).toBe(409)
    expect(apiError.code).toBe('session_exists')
    expect(apiError.detail).toBe('A session already exists for today.')
    expect(apiError.body.session_id).toBe('s-1')
  })

  it('derives a default code when the error body has none', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('Forbidden', { status: 403, headers: { 'Content-Type': 'text/plain' } }),
    )
    let caught: unknown
    try {
      await api.get('/me/')
    } catch (error) {
      caught = error
    }
    const apiError = caught as ApiError
    expect(apiError.status).toBe(403)
    expect(apiError.code).toBe('permission_denied')
    expect(apiError.detail).toBe('Forbidden')
  })
})
