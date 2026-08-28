<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/components/ui'
import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const auth = useAuthStore()

async function handleLogin() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = 'Please enter username and password'
    return
  }

  try {
    loading.value = true
    await auth.login({ username: username.value, password: password.value })
    password.value = ''
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : 'Authentication service unavailable'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen grid place-items-center bg-slate-50">
    <Card class="w-full max-w-md">
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <p class="text-sm text-muted-foreground mt-2">Use your LDAP/Windows session credentials</p>
      </CardHeader>
      <CardContent class="space-y-4">
        <div class="space-y-2">
          <label class="text-sm font-medium">Username</label>
          <input
            v-model="username"
            type="text"
            class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>
        <div class="space-y-2">
          <label class="text-sm font-medium">Password</label>
          <input
            v-model="password"
            type="password"
            class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>
        <div v-if="error" class="text-sm text-red-500">{{ error }}</div>
        <Button @click="handleLogin" class="w-full" :disabled="loading">{{ loading ? 'Signing in…' : 'Sign in' }}</Button>
      </CardContent>
    </Card>
  </div>
</template>
