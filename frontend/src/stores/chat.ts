import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../utils/api'
import { useAuthStore } from './auth'

export type ChatMode = 'file' | 'kb' | 'analysis'

const API = ''

interface Conversation {
  id: number
  title: string
  mode: ChatMode
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
  const currentMode = ref<ChatMode>('file')
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const suggestedQuestions = ref<string[]>([])
  const selectedFile = ref<string | null>(null)
  const _selectedFilesByConv = new Map<number, string | null>()

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConvId.value)
  )

  function conversationsByMode(mode: ChatMode) {
    return computed(() => conversations.value.filter(c => (c.mode || 'file') === mode))
  }

  async function loadConversations(mode?: ChatMode, _force = false) {
    const auth = useAuthStore()
    try {
      const params: Record<string, string> = {}
      if (mode) params.mode = mode
      const res = await api.get(`${API}/conversations`, {
        headers: auth.getAuthHeaders(),
        params
      })
      conversations.value = res.data
    } catch {
      // Silently fail — user sees empty conversation list
    }
  }

  async function createConversation(mode: ChatMode = 'file') {
    const auth = useAuthStore()
    currentMode.value = mode
    // Save current selection before switching
    if (currentConvId.value !== null) {
      _selectedFilesByConv.set(currentConvId.value, selectedFile.value)
    }
    const res = await api.post(`${API}/conversations`, { mode }, {
      headers: auth.getAuthHeaders()
    })
    conversations.value.unshift(res.data)
    currentConvId.value = res.data.id
    messages.value = []
    selectedFile.value = null
    return res.data
  }

  async function selectConversation(id: number) {
    const auth = useAuthStore()
    // Save current selection for the previous conversation
    if (currentConvId.value !== null) {
      _selectedFilesByConv.set(currentConvId.value, selectedFile.value)
    }
    currentConvId.value = id
    // Restore selection for this conversation
    selectedFile.value = _selectedFilesByConv.has(id) ? _selectedFilesByConv.get(id)! : null
    const res = await api.get(`${API}/conversations/${id}/messages`, {
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
    await api.delete(`${API}/conversations/${id}`, {
      headers: auth.getAuthHeaders()
    })
    conversations.value = conversations.value.filter(c => c.id !== id)
    _selectedFilesByConv.delete(id)
    if (currentConvId.value === id) {
      currentConvId.value = null
      messages.value = []
      selectedFile.value = null
    }
  }

  function selectFile(name: string | null) {
    selectedFile.value = name
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
      const payload: Record<string, any> = {
        question,
        conversation_id: currentConvId.value,
        session_id: currentConvId.value ? `conv_${currentConvId.value}` : undefined
      }
      if (selectedFile.value) {
        payload.doc_name = selectedFile.value
      }

      const response = await fetch(`${API}/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...auth.getAuthHeaders()
        },
        body: JSON.stringify(payload)
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
            }
          } catch {}
        }
      }

      assistantMsg.sources = sources

      // Reload conversations to update title
      await loadConversations(currentMode.value, true)

      // Fetch suggested follow-up questions after streaming completes
      if (answer) {
        try {
          const suggestRes = await fetch(`${API}/suggest`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...auth.getAuthHeaders()
            },
            body: JSON.stringify({ question, answer })
          })
          if (suggestRes.ok) {
            const suggestData = await suggestRes.json()
            suggestedQuestions.value = suggestData.questions || []
          }
        } catch {
          // Suggestions are non-critical, ignore errors
        }
      }

    } catch (err) {
      assistantMsg.content = '请求失败，请稍后重试。'
    } finally {
      isStreaming.value = false
    }
  }

  async function sendFeedback(messageIndex: number, value: 'positive' | 'negative') {
    const msg = messages.value[messageIndex]
    if (!msg) return

    // Toggle: clicking the same feedback again cancels it visually
    const newValue = msg.feedback === value ? undefined : value
    msg.feedback = newValue

    if (msg.id) {
      const auth = useAuthStore()
      try {
        await api.post(`${API}/feedback`, {
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
      const res = await api.post(`${API}/regenerate`, {
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
    currentMode,
    messages,
    isStreaming,
    suggestedQuestions,
    selectedFile,
    currentConversation,
    conversationsByMode,
    loadConversations,
    createConversation,
    selectConversation,
    deleteConversation,
    selectFile,
    sendMessage,
    sendFeedback,
    regenerate
  }
})
