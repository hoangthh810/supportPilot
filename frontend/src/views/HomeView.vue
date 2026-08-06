<script setup lang="ts">
import { computed, ref } from 'vue'

import { createPublicApiClient } from '@/services/api'
import { WalkingSkeletonApi } from '@/services/walkingSkeleton'
import { useSessionStore } from '@/stores/session'
import type {
  AgentRunResponse,
  ApprovalDecisionResponse,
  ApprovalDetail,
  TicketCreateResponse,
} from '@/types/api'

const session = useSessionStore()
const api = new WalkingSkeletonApi(createPublicApiClient())

const subject = ref('Đã thanh toán nhưng đơn chưa xác nhận')
const body = ref('Tôi đã thanh toán cái ghế nhưng trạng thái vẫn pending.')
const ticket = ref<TicketCreateResponse | null>(null)
const run = ref<AgentRunResponse | null>(null)
const approval = ref<ApprovalDetail | null>(null)
const result = ref<ApprovalDecisionResponse | null>(null)
const busy = ref(false)
const error = ref<string | null>(null)

const actorLabel = computed(() => session.actor?.role.replaceAll('_', ' ') ?? 'signed out')

async function perform<T>(operation: () => Promise<T>): Promise<T | null> {
  busy.value = true
  error.value = null
  try {
    return await operation()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'The demo request failed.'
    return null
  } finally {
    busy.value = false
  }
}

async function loginCustomer(): Promise<void> {
  const response = await perform(() =>
    api.login({ email: 'customer@example.test', password: 'demo-password' }),
  )
  if (response) session.setSession(response)
}

async function createTicket(): Promise<void> {
  const response = await perform(() =>
    api.createTicket(
      { subject: subject.value, body: body.value, source: 'web' },
      `ticket-${crypto.randomUUID()}`,
    ),
  )
  if (response) ticket.value = response
}

async function startReview(): Promise<void> {
  if (!ticket.value) return
  const runResponse = await perform(() =>
    api.createRun(ticket.value!.ticket_id, `run-${crypto.randomUUID()}`),
  )
  if (!runResponse) return
  run.value = runResponse

  const reviewer = await perform(() =>
    api.login({ email: 'agent@example.test', password: 'demo-password' }),
  )
  if (!reviewer) return
  session.setSession(reviewer)
  approval.value = await perform(() => api.getApproval(runResponse.approval_request_id))
}

async function decide(decision: 'approve' | 'reject'): Promise<void> {
  if (!approval.value) return
  result.value = await perform(() =>
    api.decide(approval.value!.approval_id, {
      decision,
      reason: decision === 'approve' ? 'Synthetic evidence supports sync.' : 'Escalate for review.',
      expected_version: approval.value!.proposal_version,
      expected_proposal_hash: approval.value!.proposal_hash,
      edited_action: null,
    }),
  )
}
</script>

<template>
  <section class="demo" aria-labelledby="skeleton-title">
    <div>
      <p class="eyebrow">Walking Skeleton · synthetic data only</p>
      <h1 id="skeleton-title">Payment Mismatch review</h1>
      <p class="summary">
        PostgreSQL Ticket persistence with fixed proposal, fake review and deterministic verification.
      </p>
      <p class="actor">Current demo role: <strong>{{ actorLabel }}</strong></p>
    </div>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <article class="card">
      <h2>1. Customer Ticket</h2>
      <button v-if="!session.isAuthenticated" :disabled="busy" @click="loginCustomer">
        Sign in as demo customer
      </button>
      <form v-else-if="!ticket" @submit.prevent="createTicket">
        <label>
          Subject
          <input v-model="subject" required />
        </label>
        <label>
          Message
          <textarea v-model="body" required rows="4" />
        </label>
        <button :disabled="busy">Create Ticket</button>
      </form>
      <p v-else><strong>{{ ticket.ticket_number }}</strong> · {{ ticket.ticket_status }}</p>
    </article>

    <article v-if="ticket" class="card">
      <h2>2. Explicit Agent Run</h2>
      <button v-if="!run" :disabled="busy" @click="startReview">Create Agent Run</button>
      <p v-else>{{ run.run_status }} · next: {{ run.next_required_action }}</p>
    </article>

    <article v-if="approval" class="card">
      <h2>3. Reviewer decision</h2>
      <p>{{ approval.summary }}</p>
      <ul>
        <li v-for="item in approval.evidence" :key="item">{{ item }}</li>
      </ul>
      <pre>{{ JSON.stringify(approval.action, null, 2) }}</pre>
      <div class="actions">
        <button :disabled="busy || !!result" @click="decide('approve')">Approve</button>
        <button class="secondary" :disabled="busy || !!result" @click="decide('reject')">
          Reject
        </button>
      </div>
    </article>

    <article v-if="result" class="card result" aria-live="polite">
      <h2>4. Ticket result</h2>
      <p><strong>{{ result.ticket_status }}</strong> · run {{ result.run_status }}</p>
      <p v-if="result.action_execution_status">
        Fake action: {{ result.action_execution_status }} (not release evidence)
      </p>
    </article>
  </section>
</template>

<style scoped>
.demo {
  display: grid;
  gap: 20px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #52637a;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2rem, 6vw, 3.5rem);
}

.summary {
  max-width: 44rem;
  color: #52637a;
  font-size: 1.125rem;
}

.actor {
  color: #52637a;
}

.card {
  padding: 24px;
  border: 1px solid #dce3ed;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 24px rgb(23 32 51 / 6%);
}

.card h2 {
  margin-top: 0;
}

form,
label {
  display: grid;
  gap: 8px;
}

form {
  gap: 16px;
}

input,
textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #b9c5d4;
  border-radius: 8px;
}

button {
  width: fit-content;
  padding: 10px 16px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  background: #2457d6;
  cursor: pointer;
}

button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.secondary {
  background: #66758b;
}

.actions {
  display: flex;
  gap: 12px;
}

pre {
  overflow: auto;
  padding: 16px;
  border-radius: 8px;
  background: #eef2f8;
}

.result {
  border-color: #6bbf8a;
}

.error {
  padding: 12px 16px;
  border-radius: 8px;
  color: #8f1d1d;
  background: #feecec;
}
</style>
