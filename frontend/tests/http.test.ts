import { describe, expect, it, vi } from 'vitest'

import { assertPublicApiBaseUrl, PublicApiClient } from '@/services/http'
import type { CorrelationEnvelope } from '@/types/api'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  return new Response(JSON.stringify(body), { ...init, headers })
}

describe('PublicApiClient', () => {
  it('accepts only the public API prefix', () => {
    expect(assertPublicApiBaseUrl('/api/v1')).toBe('/api/v1')
    expect(() => assertPublicApiBaseUrl('/internal/v1')).toThrow('/api/v1')
    expect(() => assertPublicApiBaseUrl('https://user:secret@example.test/api/v1')).toThrow(
      '/api/v1',
    )
  })

  it('propagates correlation and the user access token', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers)
      return jsonResponse({ correlation_id: headers.get('X-Correlation-ID') })
    })
    const fetchImplementation = fetchMock as typeof fetch
    const client = new PublicApiClient({
      fetchImplementation,
      getAccessToken: () => 'user-access-token',
    })

    const result = await client.request<CorrelationEnvelope>('GET', '/health')
    const [url, init] = fetchMock.mock.calls[0] ?? []
    const headers = new Headers(init?.headers)

    expect(url).toBe('/api/v1/health')
    expect(headers.get('Authorization')).toBe('Bearer user-access-token')
    expect(headers.get('X-Correlation-ID')).toBe(result.correlation_id)
  })

  it('omits Authorization when there is no user session', async () => {
    const fetchImplementation = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers)
      expect(headers.has('Authorization')).toBe(false)
      return jsonResponse({ correlation_id: headers.get('X-Correlation-ID') })
    }) as typeof fetch

    await new PublicApiClient({ fetchImplementation }).request<CorrelationEnvelope>('GET', '/health')
  })

  it('maps the approved error envelope without leaking response internals', async () => {
    const fetchImplementation = vi.fn(async () =>
      jsonResponse(
        {
          code: 'ACCOUNT_DISABLED',
          message: 'The account is unavailable.',
          retryable: false,
          correlation_id: 'corr_disabled',
          details: {},
        },
        { status: 403 },
      ),
    ) as typeof fetch

    const promise = new PublicApiClient({ fetchImplementation }).request('GET', '/me')

    await expect(promise).rejects.toMatchObject({
      status: 403,
      code: 'ACCOUNT_DISABLED',
      retryable: false,
      correlationId: 'corr_disabled',
    })
  })

  it('rejects paths that can escape the configured public prefix', async () => {
    const fetchImplementation = vi.fn() as unknown as typeof fetch
    const client = new PublicApiClient({ fetchImplementation })

    await expect(client.request('GET', '//example.test')).rejects.toThrow('relative')
    expect(fetchImplementation).not.toHaveBeenCalled()
  })
})
