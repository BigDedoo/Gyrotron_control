import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // Initialize from local storage
  const u = localStorage.getItem('gyro_user')
  const r = localStorage.getItem('gyro_role')
  const user = ref<{ username: string; role: string } | null>(
    u && r ? { username: u, role: r } : null
  )

  function setUser(username: string, role: string) {
    localStorage.setItem('gyro_user', username)
    localStorage.setItem('gyro_role', role)
    user.value = { username, role }
  }

  function logout() {
    localStorage.removeItem('gyro_user')
    localStorage.removeItem('gyro_role')
    user.value = null
  }

  async function login(creds: { username: string; password: string }) {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(creds)
    })

    if (!response.ok) {
      if (response.status === 401) throw new Error('Invalid credentials')
      if (response.status === 403) throw new Error('Access denied')
      throw new Error('Login failed')
    }

    const data = await response.json()
    setUser(data.username, data.role)
    return true
  }

  return { user, login, logout }
})
