<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Trash2, UserPlus, Users } from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui'
import { api, ApiError } from '@/api/client'
import type { UserRecord, UserRole } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const users = ref<UserRecord[]>([])
const newUser = ref('')
const newRole = ref<UserRole>('user')
const loading = ref(false)
const error = ref('')

const message = (caught: unknown, fallback: string) => caught instanceof ApiError ? caught.message : fallback
async function fetchUsers() {
  try { users.value = await api.getUsers(); error.value = '' }
  catch (caught) { if (caught instanceof ApiError && caught.status === 401) auth.clearSession(); else error.value = message(caught, 'Failed to load users') }
}
async function addUser() {
  if (!newUser.value.trim()) return
  loading.value = true
  try {
    users.value = (await api.addUser(newUser.value.trim(), newRole.value)).users
    newUser.value = ''; newRole.value = 'user'; error.value = ''
  } catch (caught) { error.value = message(caught, 'Error adding user') }
  finally { loading.value = false }
}
async function updateRole(user: UserRecord, role: UserRole) {
  loading.value = true
  try { users.value = (await api.updateUser(user.username, role)).users; error.value = '' }
  catch (caught) { error.value = message(caught, 'Error updating role'); await fetchUsers() }
  finally { loading.value = false }
}
async function removeUser(username: string) {
  if (!window.confirm(`Are you sure you want to remove ${username}?`)) return
  loading.value = true
  try { users.value = (await api.removeUser(username)).users; error.value = '' }
  catch (caught) { error.value = message(caught, 'Error removing user') }
  finally { loading.value = false }
}

onMounted(fetchUsers)
</script>

<template>
  <Card class="rounded-2xl"><CardContent class="p-6">
    <div class="flex items-center gap-4 mb-6"><div class="size-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600"><Users :size="20" /></div><div><h2 class="text-lg font-semibold">User Whitelist & Roles</h2><p class="text-sm text-slate-500">Backend-authoritative access and roles.</p></div></div>
    <form class="flex flex-wrap gap-3 items-end mb-8 bg-slate-50 p-4 rounded-xl border" @submit.prevent="addUser">
      <div class="flex-1 min-w-56 space-y-1"><label class="text-sm font-medium">Add New User</label><div class="relative"><UserPlus class="absolute left-3 top-2.5 text-slate-400" :size="16" /><input v-model="newUser" class="pl-9 flex h-10 w-full rounded-md border bg-white px-3 py-2 text-sm" placeholder="username" /></div></div>
      <div class="w-32 space-y-1"><label class="text-sm font-medium">Role</label><select v-model="newRole" class="h-10 w-full rounded-md border bg-white px-3 text-sm"><option value="user">User</option><option value="admin">Admin</option></select></div>
      <button type="submit" :disabled="loading || !newUser.trim()" class="h-10 px-4 bg-slate-900 text-white rounded-md text-sm disabled:opacity-50">{{ loading ? 'Working…' : 'Add' }}</button>
    </form>
    <div v-if="error" class="text-red-600 text-sm mb-4">{{ error }}</div>
    <div class="border rounded-xl overflow-hidden"><table class="w-full text-sm text-left"><thead class="bg-slate-50 border-b"><tr><th class="px-4 py-3">Username</th><th class="px-4 py-3">Role</th><th class="px-4 py-3 text-center">Action</th></tr></thead><tbody class="divide-y"><tr v-for="user in users" :key="user.username"><td class="px-4 py-3 font-medium">{{ user.username }}</td><td class="px-4 py-3"><select :value="user.role" :disabled="loading" class="rounded border px-2 py-1 text-xs" @change="updateRole(user, ($event.target as HTMLSelectElement).value as UserRole)"><option value="user">User</option><option value="admin">Admin</option></select></td><td class="px-4 py-3 text-center"><button :disabled="loading" class="p-2 text-slate-400 hover:text-red-600" title="Remove user" @click="removeUser(user.username)"><Trash2 :size="16" /></button></td></tr><tr v-if="users.length === 0"><td colspan="3" class="px-4 py-8 text-center text-slate-500">No users in whitelist.</td></tr></tbody></table></div>
  </CardContent></Card>
</template>
