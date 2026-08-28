import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { SessionUser } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<SessionUser | null>(null)
  const initialized = ref(false)

  function clearSession() {
    user.value = null
  }

  async function initializeSession() {
    try {
      user.value = await api.getSession()
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) console.error('Session check failed')
      clearSession()
    } finally {
      initialized.value = true
    }
  }

  async function login(creds: { username: string; password: string }) {
    user.value = await api.login(creds.username, creds.password)
    return user.value
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      clearSession()
    }
  }

  return { user, initialized, initializeSession, login, logout, clearSession }
})
