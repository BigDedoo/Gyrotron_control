<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { ArrowRight, TriangleAlert } from 'lucide-vue-next'
import { api, ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import StatusPill from '@/components/hmi/StatusPill.vue'
import type { EquipmentId, EventRecord, EventState } from '@/api/types'

const props = defineProps<{ active: boolean }>()
defineEmits<{ history: [] }>()
const auth = useAuthStore()
const events = ref<EventRecord[]>([])
const loading = ref(false)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined

const visible = computed(() => [...events.value]
  .sort((a, b) => new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime() || b.id - a.id)
  .slice(0, 10))
const criticalCount = computed(() => visible.value.filter((event) => event.severity === 'critical').length)
const warningCount = computed(() => visible.value.filter((event) => event.severity === 'warning').length)

const equipmentLabels: Record<EquipmentId, string> = {
  system: 'SYSTEM',
  cmps: 'CMPS',
  cfps: 'CFPS',
  ipps: 'IPPS',
  arc_detector: 'Arc Detector',
  ahvps: 'AHVPS',
  chvps: 'CHVPS',
  pulse_generator: 'Pulse Generator'
}
const legacyEquipmentTargets: Record<string, string> = {
  'interlock.cmps': 'CMPS',
  'interlock.ipps': 'IPPS',
  'alarm.arc_detector': 'Arc Detector',
  'alarm.overvoltage': 'AHVPS',
  'interlock.ahvps': 'AHVPS',
  'interlock.chvps': 'CHVPS',
  'cfps.feedback': 'CFPS',
  'ahvps.protection': 'AHVPS',
  'chvps.protection': 'CHVPS'
}

function equipment(event: EventRecord) {
  if (event.equipment) return equipmentLabels[event.equipment]
  return event.target ? legacyEquipmentTargets[event.target] ?? 'SYSTEM' : 'SYSTEM'
}
function eventState(event: EventRecord): EventState {
  if (event.state) return event.state
  const to = typeof event.details.to === 'string' ? event.details.to.toLowerCase() : ''
  if (event.event_type.includes('cleared') || event.event_type.includes('recovered') || ['ok', 'inactive', 'live'].includes(to)) return 'recovered'
  if (event.event_type.includes('activated') || event.event_type.includes('connection_lost') || event.event_type === 'monitor.error' || ['fault', 'active', 'degraded', 'stale', 'unavailable'].includes(to)) return 'active'
  return 'changed'
}
function compactTime(recordedAt: string) {
  const date = new Date(recordedAt)
  const now = new Date()
  const sameDay = date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate()
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  return sameDay ? time : `${date.toLocaleDateString([], { month: '2-digit', day: '2-digit' })} ${time}`
}
function detailText(event: EventRecord) {
  const details: string[] = []
  const from = event.details.from
  const to = event.details.to
  if (typeof from === 'string' && typeof to === 'string') details.push(`${from.toUpperCase()} → ${to.toUpperCase()}`)
  for (const key of ['reason', 'connection_state', 'data_state'] as const) {
    const value = event.details[key]
    if (typeof value === 'string' && !details.includes(value)) details.push(value.replace(/_/g, ' '))
  }
  if (event.target) details.push(event.target)
  else if (event.source) details.push(event.source)
  return details.slice(0, 2).join(' · ') || '—'
}

async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    const [warnings, criticals] = await Promise.all([
      api.getEvents({ limit: 10, severity: 'warning' }),
      api.getEvents({ limit: 10, severity: 'critical' })
    ])
    const merged = new Map<number, EventRecord>()
    ;[...warnings.events, ...criticals.events].forEach((event) => merged.set(event.id, event))
    events.value = [...merged.values()]
    error.value = ''
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 401) auth.clearSession()
    else error.value = caught instanceof ApiError ? caught.message : 'Recent problem history is unavailable.'
  } finally {
    loading.value = false
  }
}
function schedule() {
  if (timer) clearTimeout(timer)
  if (!props.active) return
  timer = setTimeout(async () => { await refresh(); schedule() }, 10000)
}
watch(() => props.active, async (active) => {
  if (timer) clearTimeout(timer)
  if (active) { await refresh(); schedule() }
}, { immediate: true })
onScopeDispose(() => { if (timer) clearTimeout(timer) })
</script>

<template>
  <section class="rounded border bg-white shadow-sm">
    <div class="flex items-center justify-between border-b px-3 py-2">
      <div class="flex items-center gap-3">
        <h2 class="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-700"><TriangleAlert class="size-4" /> Recent Problems</h2>
        <span v-if="visible.length" class="text-[10px] text-slate-400">{{ criticalCount }} critical · {{ warningCount }} warning</span>
      </div>
      <button class="flex items-center gap-1 text-[10px] font-semibold text-blue-700 hover:text-blue-900" @click="$emit('history')">View full history <ArrowRight class="size-3" /></button>
    </div>
    <div v-if="error" class="px-3 py-3 text-xs text-amber-700">{{ error }}</div>
    <div v-else-if="loading && !visible.length" class="px-3 py-3 text-xs text-slate-500">Loading recent problem history…</div>
    <div v-else-if="!visible.length" class="px-3 py-3 text-xs text-emerald-700">No recent warning or critical events</div>
    <div v-else class="overflow-x-auto">
      <table class="w-full min-w-[860px] table-fixed text-left">
        <thead class="bg-slate-50 text-[9px] uppercase tracking-[0.12em] text-slate-400">
          <tr><th class="w-28 px-3 py-1.5">Time</th><th class="w-24 px-3 py-1.5">Severity</th><th class="w-24 px-3 py-1.5">State</th><th class="w-28 px-3 py-1.5">Equipment</th><th class="w-[32%] px-3 py-1.5">Problem</th><th class="px-3 py-1.5">Details</th></tr>
        </thead>
        <tbody class="divide-y divide-slate-100 text-[11px]">
          <tr v-for="event in visible" :key="event.id" :class="eventState(event) === 'recovered' ? 'border-l-2 border-l-emerald-400 bg-emerald-50/30' : event.severity === 'critical' ? 'border-l-2 border-l-red-500 bg-red-50/30' : 'border-l-2 border-l-amber-400 hover:bg-slate-50'">
            <td class="whitespace-nowrap px-3 py-1.5 font-mono text-[10px] text-slate-500">{{ compactTime(event.recorded_at) }}</td>
            <td class="px-3 py-1.5"><span :class="['rounded border px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wide', event.severity === 'critical' ? 'border-red-300 bg-red-100 text-red-800' : 'border-amber-300 bg-amber-100 text-amber-800']">{{ event.severity }}</span></td>
            <td class="px-3 py-1.5"><StatusPill :state="eventState(event)" /></td>
            <td class="truncate px-3 py-1.5 font-semibold text-slate-600">{{ equipment(event) }}</td>
            <td class="truncate px-3 py-1.5 font-medium text-slate-800" :title="event.message">{{ event.message }}</td>
            <td class="truncate px-3 py-1.5 text-slate-500" :title="detailText(event)">{{ detailText(event) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
