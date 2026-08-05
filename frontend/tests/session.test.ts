import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useSessionStore } from '@/stores/session'

describe('session store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('keeps the user access token in memory and clears it', () => {
    const store = useSessionStore()
    store.setSession({
      access_token: 'user-access-token',
      token_type: 'Bearer',
      expires_in_seconds: 900,
      actor: { id: 'actor-1', role: 'customer', status: 'active' },
      correlation_id: 'corr_login',
    })

    expect(store.isAuthenticated).toBe(true)
    expect(store.hasRole('customer')).toBe(true)
    expect(store.hasRole('admin')).toBe(false)

    store.clearSession()
    expect(store.isAuthenticated).toBe(false)
    expect(store.accessToken).toBeNull()
  })
})

