import { defineStore } from 'pinia'

import type { Actor, ActorRole, LoginResponse } from '@/types/api'

interface SessionState {
  accessToken: string | null
  actor: Actor | null
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    accessToken: null,
    actor: null,
  }),
  getters: {
    isAuthenticated: (state): boolean => state.accessToken !== null && state.actor !== null,
  },
  actions: {
    setSession(response: LoginResponse): void {
      this.accessToken = response.access_token
      this.actor = response.actor
    },
    clearSession(): void {
      this.accessToken = null
      this.actor = null
    },
    hasRole(role: ActorRole): boolean {
      // UX visibility only. Backend authorization remains authoritative.
      return this.actor?.role === role
    },
  },
})

