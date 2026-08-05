import { PublicApiClient } from '@/services/http'
import { useSessionStore } from '@/stores/session'

export function createPublicApiClient(): PublicApiClient {
  const session = useSessionStore()
  return new PublicApiClient({
    getAccessToken: () => session.accessToken,
  })
}

