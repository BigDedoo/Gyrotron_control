<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/components/ui'

const username = ref('')
const password = ref('')
const error = ref('')

const emit = defineEmits<{
  (e: 'login', username: string, role: string): void
}>()

async function handleLogin() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = 'Please enter username and password'
    return
  }

  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value })
    })

    if (!response.ok) {
        if (response.status === 401) throw new Error('Invalid credentials')
        if (response.status === 403) throw new Error('Access denied')
        throw new Error('Login failed')
    }

    const data = await response.json()
    emit('login', data.username, data.role)
  } catch (e: any) {
    error.value = e.message || 'An error occurred'
  }
}
</script>

<template>
  <div class="min-h-screen grid place-items-center bg-slate-50">
    <Card class="w-full max-w-md">
      <CardHeader>
        <CardTitle>Login</CardTitle>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="space-y-2">
          <label class="text-sm font-medium">Username</label>
          <input v-model="username" type="text" class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50" />
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium">Password</label>
          <input v-model="password" type="password" class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50" />
        </div>
        <div v-if="error" class="text-sm text-red-500">{{ error }}</div>
        <Button @click="handleLogin" class="w-full">Sign In</Button>
      </CardContent>
    </Card>
  </div>
</template>
