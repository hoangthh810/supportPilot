import { describe, expect, it, vi } from 'vitest'

import { PublicApiClient } from '@/services/http'
import { WalkingSkeletonApi } from '@/services/walkingSkeleton'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('WalkingSkeletonApi', () => {
  it('uses only final public API paths and user Bearer auth', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path.endsWith('/auth/login')) {
        return jsonResponse({
          access_token: 'customer-token',
          token_type: 'Bearer',
          expires_in_seconds: 900,
          actor: { id: 'actor-id', role: 'customer', status: 'active' },
          correlation_id: 'corr-login',
        })
      }
      if (path.endsWith('/tickets')) {
        return jsonResponse({
          ticket_id: 'ticket-id',
          ticket_number: 'SP-000001',
          ticket_status: 'OPEN',
          correlation_id: 'corr-ticket',
        })
      }
      return jsonResponse({
        run_id: 'run-id',
        run_status: 'WAITING_APPROVAL',
        ticket_status: 'WAITING_APPROVAL',
        next_required_action: 'approval',
        approval_request_id: 'approval-id',
        correlation_id: 'corr-run',
        timeline_cursor: 'cursor',
      })
    })
    const api = new WalkingSkeletonApi(
      new PublicApiClient({
        fetchImplementation: fetchMock as typeof fetch,
        getAccessToken: () => 'customer-token',
      }),
    )

    await api.login({ email: 'customer@example.test', password: 'demo-password' })
    await api.createTicket(
      { subject: 'Payment mismatch', body: 'Synthetic fixture', source: 'web' },
      'ticket-key',
    )
    await api.createRun('ticket-id', 'run-key')

    const calls = fetchMock.mock.calls
    expect(calls.map(([url]) => String(url))).toEqual([
      '/api/v1/auth/login',
      '/api/v1/tickets',
      '/api/v1/tickets/ticket-id/agent-runs',
    ])
    expect(new Headers(calls[1]?.[1]?.headers).get('Idempotency-Key')).toBe('ticket-key')
    expect(new Headers(calls[2]?.[1]?.headers).get('Authorization')).toBe(
      'Bearer customer-token',
    )
    expect(calls.every(([url]) => !String(url).includes('/internal/'))).toBe(true)
  })
})
