import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

vi.mock('../../utils/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn()
  }
}))

import api from '../../utils/api'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.clearAllMocks()
})

describe('auth store', () => {
  it('login success saves token and sets user', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { token: 'abc123', username: 'testuser' }
    } as any)

    const store = useAuthStore()
    await store.login('testuser', 'password')

    expect(store.token).toBe('abc123')
    expect(store.user).toEqual({ id: 0, username: 'testuser' })
    expect(localStorage.getItem('rag_token')).toBe('abc123')
  })

  it('login failure throws error', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('Invalid credentials'))

    const store = useAuthStore()
    await expect(store.login('wrong', 'creds')).rejects.toThrow('Invalid credentials')
    expect(store.token).toBe('')
  })

  it('fetchUser success sets user', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { id: 1, username: 'alice' }
    } as any)

    const store = useAuthStore()
    store.token = 'valid-token'
    await store.fetchUser()

    expect(store.user).toEqual({ id: 1, username: 'alice' })
  })

  it('fetchUser 401 triggers logout', async () => {
    const error = new Error('Unauthorized') as any
    error.response = { status: 401 }
    vi.mocked(api.get).mockRejectedValue(error)

    const store = useAuthStore()
    store.token = 'expired-token'

    await store.fetchUser()

    expect(store.token).toBe('')
    expect(store.user).toBeNull()
    expect(localStorage.getItem('rag_token')).toBeNull()
  })

  it('logout clears token and user', () => {
    const store = useAuthStore()
    store.token = 'some-token'
    store.user = { id: 1, username: 'bob' }

    store.logout()

    expect(store.token).toBe('')
    expect(store.user).toBeNull()
    expect(localStorage.getItem('rag_token')).toBeNull()
  })
})
