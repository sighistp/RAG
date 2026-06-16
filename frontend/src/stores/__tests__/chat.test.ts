import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../chat'

vi.mock('../../utils/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('../auth', () => ({
  useAuthStore: vi.fn(() => ({
    token: 'test-token',
    getAuthHeaders: () => ({ Authorization: 'Bearer test-token' })
  }))
}))

import api from '../../utils/api'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('chat store', () => {
  it('loadConversations fills the list', async () => {
    const convos = [
      { id: 1, title: 'First', created_at: '2026-01-01' },
      { id: 2, title: 'Second', created_at: '2026-01-02' }
    ]
    vi.mocked(api.get).mockResolvedValue({ data: convos } as any)

    const store = useChatStore()
    await store.loadConversations()

    expect(store.conversations).toEqual(convos)
  })

  it('createConversation adds to list and sets currentConvId', async () => {
    const newConv = { id: 3, title: 'New', created_at: '2026-01-03' }
    vi.mocked(api.post).mockResolvedValue({ data: newConv } as any)

    const store = useChatStore()
    const result = await store.createConversation()

    expect(result).toEqual(newConv)
    expect(store.conversations[0]).toEqual(newConv)
    expect(store.currentConvId).toBe(3)
  })

  it('deleteConversation removes from list', async () => {
    const store = useChatStore()
    store.conversations = [
      { id: 1, title: 'A', created_at: '2026-01-01' },
      { id: 2, title: 'B', created_at: '2026-01-02' }
    ]
    store.currentConvId = 1

    vi.mocked(api.delete).mockResolvedValue({} as any)

    await store.deleteConversation(1)

    expect(store.conversations.find(c => c.id === 1)).toBeUndefined()
    expect(store.currentConvId).toBeNull()
  })

  it('selectConversation sets currentConvId', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] } as any)

    const store = useChatStore()
    await store.selectConversation(5)

    expect(store.currentConvId).toBe(5)
  })

  it('sendMessage calls /query/stream via fetch', async () => {
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode('data: {"type":"token","content":"Hi"}\n')
            })
            .mockResolvedValueOnce({ done: true, value: undefined })
        })
      }
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockResponse as any)
    vi.mocked(api.get).mockResolvedValue({ data: [] } as any)

    const store = useChatStore()
    await store.sendMessage('Hello')

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/query/stream',
      expect.objectContaining({ method: 'POST' })
    )
    expect(store.messages).toHaveLength(2)
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[1].role).toBe('assistant')
  })

  it('sendFeedback calls /feedback', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: {} } as any)

    const store = useChatStore()
    store.messages = [{ id: 10, role: 'assistant', content: 'Answer' }]

    await store.sendFeedback(0, 'positive')

    expect(api.post).toHaveBeenCalledWith(
      '/feedback',
      { message_id: 10, value: 'positive' },
      expect.anything()
    )
    expect(store.messages[0].feedback).toBe('positive')
  })

  it('regenerate calls /regenerate', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { answer: 'New answer' } } as any)

    const store = useChatStore()
    store.currentConvId = 7
    store.messages = [{ id: 20, role: 'assistant', content: 'Old' }]

    await store.regenerate(0)

    expect(api.post).toHaveBeenCalledWith(
      '/regenerate',
      { conversation_id: 7, message_id: 20 },
      expect.anything()
    )
    expect(store.messages[0].content).toBe('New answer')
  })
})
