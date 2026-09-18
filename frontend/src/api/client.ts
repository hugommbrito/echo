import type { ApiErrorBody, CsrfResponse } from '@/types/api'

export const API_BASE = '/api/v1'
const CSRF_COOKIE = 'csrftoken'
const CSRF_HEADER = 'X-CSRFToken'
const UNSAFE_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE'])

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: string
  readonly errors?: Record<string, string[]>
  /** Whole parsed body — conflicts may carry extra keys (e.g. `session_id`). */
  readonly body: Partial<ApiErrorBody>

  constructor(status: number, body: Partial<ApiErrorBody>) {
    const detail = typeof body.detail === 'string' ? body.detail : `Erro HTTP ${status}`
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.code = typeof body.code === 'string' ? body.code : defaultCode(status)
    this.errors = body.errors
    this.body = body
  }

  /** First validation message for a field, if any. */
  fieldError(field: string): string | undefined {
    return this.errors?.[field]?.[0]
  }
}

function defaultCode(status: number): string {
  if (status === 401) return 'unauthenticated'
  if (status === 403) return 'permission_denied'
  if (status === 404) return 'not_found'
  if (status >= 500) return 'server_error'
  return 'error'
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export function readCookie(name: string, source: string = document.cookie): string | null {
  if (!source) return null
  for (const part of source.split(';')) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) return decodeURIComponent(rest.join('='))
  }
  return null
}

let cachedCsrfToken: string | null = null
let csrfRequest: Promise<string | null> | null = null

async function fetchCsrfToken(): Promise<string | null> {
  if (!csrfRequest) {
    csrfRequest = fetch(`${API_BASE}/auth/csrf/`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(async (res) => {
        if (!res.ok) return null
        const data = (await res.json()) as CsrfResponse
        cachedCsrfToken = data.csrfToken ?? null
        return cachedCsrfToken
      })
      .catch(() => null)
      .finally(() => {
        csrfRequest = null
      })
  }
  return csrfRequest
}

/** Cookie first; otherwise ask the backend once and cache the returned token. */
export async function getCsrfToken(): Promise<string | null> {
  const fromCookie = readCookie(CSRF_COOKIE)
  if (fromCookie) return fromCookie
  if (cachedCsrfToken) return cachedCsrfToken
  return fetchCsrfToken()
}

/** Forget the cached token (after logout, or when the server rejects it). */
export function resetCsrfToken(): void {
  cachedCsrfToken = null
}

export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue | QueryValue[]>

export function buildQuery(params?: QueryParams): string {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      const joined = value.filter((v) => v !== undefined && v !== null && v !== '').join(',')
      if (joined) search.set(key, joined)
    } else {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  query?: QueryParams
  signal?: AbortSignal
  headers?: Record<string, string>
}

async function parseBody(response: Response): Promise<unknown> {
  const type = response.headers.get('content-type') ?? ''
  if (response.status === 204) return undefined
  const text = await response.text()
  if (!text) return undefined
  if (type.includes('application/json')) {
    try {
      return JSON.parse(text) as unknown
    } catch {
      return { detail: text }
    }
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return { detail: text }
  }
}

/**
 * Fetch wrapper for the Echo API.
 * - same-origin cookies, JSON by default, multipart when `body` is FormData
 * - sends `X-CSRFToken` on unsafe methods (cookie, or `GET /auth/csrf/` once)
 * - throws `ApiError` on non-2xx; resolves `undefined` for 204
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const url = `${API_BASE}${path}${buildQuery(options.query)}`
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }

  let body: BodyInit | undefined
  if (options.body instanceof FormData) {
    body = options.body
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  if (UNSAFE_METHODS.has(method)) {
    const token = await getCsrfToken()
    if (token) headers[CSRF_HEADER] = token
  }

  const response = await fetch(url, {
    method,
    headers,
    body,
    credentials: 'same-origin',
    signal: options.signal,
  })

  if (response.status === 204) return undefined as T

  const data = await parseBody(response)

  if (!response.ok) {
    const errorBody = (
      data && typeof data === 'object' ? data : { detail: String(data ?? '') }
    ) as Partial<ApiErrorBody>
    if (response.status === 403 && errorBody.code === undefined && /CSRF/i.test(errorBody.detail ?? '')) {
      resetCsrfToken()
    }
    throw new ApiError(response.status, errorBody)
  }

  return data as T
}

export const api = {
  get: <T>(path: string, query?: QueryParams, signal?: AbortSignal) =>
    request<T>(path, { method: 'GET', query, signal }),
  post: <T>(path: string, body?: unknown, query?: QueryParams) =>
    request<T>(path, { method: 'POST', body, query }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: <T = undefined>(path: string) => request<T>(path, { method: 'DELETE' }),
}
