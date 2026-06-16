import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../utils/api'

const API = ''

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('rag_token') || '')
  const user = ref<{ id: number; username: string } | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await api.post(`${API}/login`, { username, password })
    token.value = res.data.token
    localStorage.setItem('rag_token', token.value)
    user.value = { id: 0, username: res.data.username }
    return res.data
  }

  async function register(username: string, password: string) {
    const res = await api.post(`${API}/register`, { username, password })
    token.value = res.data.token
    localStorage.setItem('rag_token', token.value)
    user.value = { id: 0, username: res.data.username }
    return res.data
  }

  async function fetchUser() {
    if (!token.value || user.value) return
    try {
      const res = await api.get(`${API}/me`, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      user.value = res.data
    } catch (err: any) {
      if (err.response?.status === 401) {
        logout()
      }
      // Other errors (network, 500) — keep token, user can retry
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('rag_token')
  }

  function getAuthHeaders() {
    return { Authorization: `Bearer ${token.value}` }
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    fetchUser,
    logout,
    getAuthHeaders
  }
})
