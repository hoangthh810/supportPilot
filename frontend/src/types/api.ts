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

