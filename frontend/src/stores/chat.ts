import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'

const API = ''

interface Conversation {
  id: number
  title: string
  created_at: string
}

interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{ doc_name: string; chunk_index: number }>
  feedback?: 'positive' | 'negative'
}

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const currentConvId = ref<number | null>(null)
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const suggestedQuestions = ref<string[]>([])
  let _loaded = false

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConvId.value)
  )

  async function loadConversations(force = false) {
    if (_loaded && !force) return
    const auth = useAuthStore()
    try {
      const res = await axios.get(`${API}/conversations`, {
        headers: auth.getAuthHeaders()
      })
      conversations.value = res.data
      _loaded = true
    } catch {
      // Silently fail — user sees empty conversation list
    }
  }

  async function createConversation() {
    const auth = useAuthStore()
    const res = await axios.post(`${API}/conversations`, {}, {
      headers: auth.getAuthHeaders()
    })
    conversations.value.unshift(res.data)
    currentConvId.value = res.data.id
    messages.value = []
    return res.data
  }

  async function selectConversation(id: number) {
    const auth = useAuthStore()
    currentConvId.value = id
    const res = await axios.get(`${API}/conversations/${id}/messages`, {
      headers: auth.getAuthHeaders()
    })
    messages.value = res.data.map((m: any) => ({
      id: m.id,
      role: m.role,
      content: m.content
    }))
  }

  async function deleteConversation(id: number) {
    const auth = useAuthStore()
    await axios.delete(`${API}/conversations/${id}`, {
      headers: auth.getAuthHeaders()
    })
    conversations.value = conversations.value.filter(c => c.id !== id)
    if (currentConvId.value === id) {
      currentConvId.value = null
      messages.value = []
    }
  }

  async function sendMessage(question: string) {
    const auth = useAuthStore()

    // Add user message
    messages.value.push({ role: 'user', content: question })
    isStreaming.value = true
    suggestedQuestions.value = []

    // Add empty assistant message for streaming
    const assistantMsg: Message = { role: 'assistant', content: '' }
    messages.value.push(assistantMsg)

    try {
      const response = await fetch(`${API}/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...auth.getAuthHeaders()
        },
        body: JSON.stringify({
          question,
          conversation_id: currentConvId.value,
          session_id: currentConvId.value ? `conv_${currentConvId.value}` : undefined
        })
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }))
        assistantMsg.content = err.detail || '请求失败'
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let answer = ''
      let sources: any[] = []
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''  // Keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'token') {
              answer += event.content
              assistantMsg.content = answer
            } else if (event.type === 'sources') {
              sources = event.sources
            } else if (event.type === 'suggested') {
              suggestedQuestions.value = event.questions || []
            }
          } catch {}
        }
      }

      assistantMsg.sources = sources

      // Reload conversations to update title
      await loadConversations(true)

    } catch (err) {
      assistantMsg.content = '请求失败，请稍后重试。'
    } finally {
      isStreaming.value = false
    }
  }

  async function sendFeedback(messageIndex: number, value: 'positive' | 'negative') {
    const msg = messages.value[messageIndex]
    if (!msg) return
    msg.feedback = value
    if (msg.id) {
      const auth = useAuthStore()
      try {
        await axios.post(`${API}/feedback`, {
          message_id: msg.id,
          value
        }, { headers: auth.getAuthHeaders() })
      } catch {
        // Ignore feedback API errors
      }
    }
  }

  async function regenerate(messageIndex: number) {
    const msg = messages.value[messageIndex]
    if (!msg || msg.role !== 'assistant' || !msg.id || !currentConvId.value) return

    const auth = useAuthStore()
    isStreaming.value = true
    try {
      const res = await axios.post(`${API}/regenerate`, {
        conversation_id: currentConvId.value,
        message_id: msg.id
      }, { headers: auth.getAuthHeaders() })
      msg.content = res.data.answer
    } catch {
      // Ignore
    } finally {
      isStreaming.value = false
    }
  }

  return {
    conversations,
    currentConvId,
    messages,
    isStreaming,
    suggestedQuestions,
    currentConversation,
    loadConversations,
    createConversation,
    selectConversation,
    deleteConversation,
    sendMessage,
    sendFeedback,
    regenerate
  }
})
