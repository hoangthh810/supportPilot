export type ActorRole = 'customer' | 'support_agent' | 'support_manager' | 'admin'

export type ActorStatus = 'active' | 'disabled'

export interface Actor {
  id: string
  role: ActorRole
  status: ActorStatus
}

export interface CorrelationEnvelope {
  correlation_id: string
}

export interface ErrorEnvelope extends CorrelationEnvelope {
  code: string
  message: string
  retryable: boolean
  details: Record<string, unknown>
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse extends CorrelationEnvelope {
  access_token: string
  token_type: 'Bearer'
  expires_in_seconds: number
  actor: Actor
}

export interface Money {
  amount: string
  currency: string
}

export interface TicketCreateRequest {
  subject: string
  body: string
  source: 'web'
}

export interface TicketCreateResponse extends CorrelationEnvelope {
  ticket_id: string
  ticket_number: string
  ticket_status: 'OPEN'
}

export interface AgentRunResponse extends CorrelationEnvelope {
  run_id: string
  run_status: 'WAITING_APPROVAL'
  ticket_status: 'WAITING_APPROVAL'
  next_required_action: 'approval'
  approval_request_id: string
  timeline_cursor: string
}

export interface ApprovalDetail extends CorrelationEnvelope {
  approval_id: string
  approval_status: string
  proposal_version: number
  proposal_hash: string
  run_id: string
  ticket_id: string
  summary: string
  action: Record<string, unknown>
  evidence: string[]
  synthetic: true
}

export interface ApprovalDecisionRequest {
  decision: 'approve' | 'reject'
  reason: string
  expected_version: number
  expected_proposal_hash: string
  edited_action: null
}

export interface ApprovalDecisionResponse extends CorrelationEnvelope {
  approval_id: string
  approval_status: 'APPROVED' | 'REJECTED'
  proposal_version: number
  proposal_hash: string
  run_id: string
  run_status: 'COMPLETED' | 'ESCALATED'
  ticket_status: 'RESOLVED' | 'ESCALATED'
  action_execution_status: 'VERIFIED' | null
  next_required_action: null
  timeline_cursor: string
}
