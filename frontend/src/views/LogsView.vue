<script setup lang="ts">
import { onScopeDispose, ref, watch } from 'vue'
import { Card, CardHeader, CardTitle, CardContent, Button, Badge } from '@/components/ui'
import { api, ApiError } from '@/api/client'
import type { AlarmSeverity, EventCategory, EventRecord } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ active: boolean }>()
const auth = useAuthStore()
const events = ref<EventRecord[]>([])
const nextBeforeId = ref<number | null>(null)
const category = ref<EventCategory | ''>('')
const severity = ref<AlarmSeverity | ''>('')
const loading = ref(false)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined

async function load(beforeId?: number) {
  if (loading.value) return
  loading.value = true
  try {
    const response = await api.getEvents({
      limit: 50,
      beforeId,
      category: category.value || undefined,
      severity: severity.value || undefined
    })
    events.value = beforeId
      ? [...events.value, ...response.events.filter((event) => !events.value.some((current) => current.id === event.id))]
      : response.events
    nextBeforeId.value = response.next_before_id
    error.value = ''
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 401) auth.clearSession()
    else error.value = caught instanceof ApiError ? caught.message : 'Event history is unavailable.'
  } finally {
    loading.value = false
  }
}

function schedule() {
  if (timer) clearTimeout(timer)
  if (!props.active) return
  timer = setTimeout(async () => { await load(); schedule() }, 5000)
}

watch([() => props.active, category, severity], async ([active]) => {
  if (timer) clearTimeout(timer)
  events.value = []
  nextBeforeId.value = null
  if (active) { await load(); schedule() }
}, { immediate: true })

onScopeDispose(() => { if (timer) clearTimeout(timer) })
</script>

<template>
  <Card class="rounded-2xl">
    <CardHeader class="pb-2 flex flex-row items-center justify-between gap-3"><CardTitle class="text-base">Backend-observed Event History</CardTitle><Button variant="outline" size="sm" :disabled="loading" @click="load()">Refresh</Button></CardHeader>
    <CardContent class="space-y-4">
      <div class="rounded-lg border border-blue-300 bg-blue-50 p-3 text-xs text-blue-900">Persistent application history of backend observations. This is not a complete PLC or safety historian.</div>
      <div class="flex flex-wrap gap-3">
        <select v-model="category" class="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">All categories</option><option v-for="value in (['application','monitoring','machine_state','interlock','alarm','security','operator','command'] as EventCategory[])" :key="value" :value="value">{{ value.replace('_', ' ') }}</option></select>
        <select v-model="severity" class="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">All severities</option><option value="info">Info</option><option value="warning">Warning</option><option value="critical">Critical</option></select>
      </div>
      <div v-if="error" class="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900">{{ error }}</div>
      <div v-else-if="loading && events.length === 0" class="text-sm text-slate-500">Loading event history…</div>
      <div v-else-if="events.length === 0" class="text-sm text-slate-500">No backend-observed events match these filters.</div>
      <div class="space-y-2">
        <div v-for="event in events" :key="event.id" class="grid grid-cols-1 gap-2 rounded-xl border bg-muted/20 px-3 py-3 md:grid-cols-12 md:items-center">
          <div class="text-xs font-mono text-slate-600 md:col-span-2">{{ new Date(event.recorded_at).toLocaleString() }}</div>
          <div class="md:col-span-2"><Badge variant="outline">{{ event.category.replace('_', ' ').toUpperCase() }}</Badge></div>
          <div class="text-sm md:col-span-6"><div class="font-medium">{{ event.message }}</div><div class="text-xs text-slate-500">{{ event.actor ? `Actor: ${event.actor}` : `Source: ${event.source}` }}{{ event.target ? ` · ${event.target}` : '' }}</div></div>
          <div class="md:col-span-2 md:text-right"><Badge v-if="event.severity" variant="outline">{{ event.severity.toUpperCase() }}</Badge><span v-else>—</span></div>
        </div>
      </div>
      <Button v-if="nextBeforeId" variant="outline" :disabled="loading" @click="load(nextBeforeId)">Load older events</Button>
    </CardContent>
  </Card>
</template>
