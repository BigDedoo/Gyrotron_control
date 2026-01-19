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
  // Mock login logic
  if (username.value && password.value) {
    // Determine role solely based on username for demo
    const role = username.value.toLowerCase().includes('admin') ? 'admin' : 'operator'
    emit('login', username.value, role)
  } else {
    error.value = 'Please enter username and password'
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
