import type { ErrorEnvelope } from '@/types/api'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
type ApiPath = `/${string}`

interface PublicApiClientOptions {
  baseUrl?: string
  fetchImplementation?: typeof fetch
  getAccessToken?: () => string | null
}

interface RequestOptions<TBody> {
  body?: TBody
  idempotencyKey?: string
  signal?: AbortSignal
}

const DEFAULT_PUBLIC_API_BASE_URL = '/api/v1'
const CORRELATION_HEADER = 'X-Correlation-ID'

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly retryable: boolean
  readonly correlationId: string
  readonly details: Record<string, unknown>

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = envelope.code
    this.retryable = envelope.retryable
    this.correlationId = envelope.correlation_id
    this.details = envelope.details
  }
}

export function assertPublicApiBaseUrl(value: string): string {
  const normalized = value.replace(/\/$/, '')
  const parsed = new URL(normalized, window.location.origin)

  if (parsed.pathname !== '/api/v1' || parsed.username || parsed.password) {
    throw new Error('VITE_PUBLIC_API_BASE_URL must target the public /api/v1 prefix')
  }
  return normalized
}

function assertApiPath(path: ApiPath): void {
  if (path.startsWith('//') || path.includes('://') || path.split('/').includes('..')) {
    throw new Error('API request path must be relative to the public API prefix')
  }
}

function newCorrelationId(): string {
  return `corr_${crypto.randomUUID().replaceAll('-', '')}`
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<ErrorEnvelope>
  return (
    typeof candidate.code === 'string' &&
    typeof candidate.message === 'string' &&
    typeof candidate.retryable === 'boolean' &&
    typeof candidate.correlation_id === 'string' &&
    typeof candidate.details === 'object' &&
    candidate.details !== null
  )
}

async function parseJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) return null
  return response.json() as Promise<unknown>
}

export class PublicApiClient {
  private readonly baseUrl: string
  private readonly fetchImplementation: typeof fetch
  private readonly getAccessToken: () => string | null

  constructor(options: PublicApiClientOptions = {}) {
    this.baseUrl = assertPublicApiBaseUrl(
      options.baseUrl ?? import.meta.env.VITE_PUBLIC_API_BASE_URL ?? DEFAULT_PUBLIC_API_BASE_URL,
    )
    this.fetchImplementation = options.fetchImplementation ?? window.fetch.bind(window)
    this.getAccessToken = options.getAccessToken ?? (() => null)
  }

  async request<TResponse, TBody = never>(
    method: HttpMethod,
    path: ApiPath,
    options: RequestOptions<TBody> = {},
  ): Promise<TResponse> {
    assertApiPath(path)
    const correlationId = newCorrelationId()
    const headers = new Headers({
      Accept: 'application/json',
      [CORRELATION_HEADER]: correlationId,
    })
    const accessToken = this.getAccessToken()

    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    if (options.body !== undefined) headers.set('Content-Type', 'application/json')
    if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey)

    const requestInit: RequestInit = {
      method,
      headers,
    }
    if (options.signal !== undefined) requestInit.signal = options.signal
    if (options.body !== undefined) requestInit.body = JSON.stringify(options.body)

    const response = await this.fetchImplementation(`${this.baseUrl}${path}`, requestInit)
    const payload = await parseJson(response)

    if (!response.ok) {
      const envelope: ErrorEnvelope = isErrorEnvelope(payload)
        ? payload
        : {
            code: 'HTTP_ERROR',
            message: 'The request could not be completed.',
            retryable: response.status >= 500,
            correlation_id: response.headers.get(CORRELATION_HEADER) ?? correlationId,
            details: {},
          }
      throw new ApiClientError(response.status, envelope)
    }

    return payload as TResponse
  }
}
