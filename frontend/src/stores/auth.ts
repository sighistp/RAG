import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const API = ''

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('rag_token') || '')
  const user = ref<{ id: number; username: string } | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await axios.post(`${API}/login`, { username, password })
    token.value = res.data.token
    localStorage.setItem('rag_token', token.value)
    user.value = { id: 0, username: res.data.username }
    return res.data
  }

  async function register(username: string, password: string) {
    const res = await axios.post(`${API}/register`, { username, password })
    token.value = res.data.token
    localStorage.setItem('rag_token', token.value)
    user.value = { id: 0, username: res.data.username }
    return res.data
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      const res = await axios.get(`${API}/me`, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      user.value = res.data
    } catch {
      logout()
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
