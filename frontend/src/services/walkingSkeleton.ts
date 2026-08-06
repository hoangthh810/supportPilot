import type {
  AgentRunResponse,
  ApprovalDecisionRequest,
  ApprovalDecisionResponse,
  ApprovalDetail,
  LoginRequest,
  LoginResponse,
  TicketCreateRequest,
  TicketCreateResponse,
} from '@/types/api'
import type { PublicApiClient } from '@/services/http'

export class WalkingSkeletonApi {
  constructor(private readonly client: PublicApiClient) {}

  login(payload: LoginRequest): Promise<LoginResponse> {
    return this.client.request('POST', '/auth/login', { body: payload })
  }

  createTicket(
    payload: TicketCreateRequest,
    idempotencyKey: string,
  ): Promise<TicketCreateResponse> {
    return this.client.request('POST', '/tickets', { body: payload, idempotencyKey })
  }

  createRun(ticketId: string, idempotencyKey: string): Promise<AgentRunResponse> {
    return this.client.request('POST', `/tickets/${ticketId}/agent-runs`, {
      body: {},
      idempotencyKey,
    })
  }

  getApproval(approvalId: string): Promise<ApprovalDetail> {
    return this.client.request('GET', `/approval-requests/${approvalId}`)
  }

  decide(
    approvalId: string,
    payload: ApprovalDecisionRequest,
  ): Promise<ApprovalDecisionResponse> {
    return this.client.request('POST', `/approval-requests/${approvalId}/decision`, {
      body: payload,
    })
  }
}
