<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Activity, ChartNoAxesCombined, Database, FileClock, Network, Shield, Users } from 'lucide-vue-next'
import StatusPill from '@/components/hmi/StatusPill.vue'
import TrendPanel from '@/components/hmi/TrendPanel.vue'
import AdminView from '@/views/AdminView.vue'
import LogsView from '@/views/LogsView.vue'
import { formatTimestamp, stateLabel } from '@/lib/hmi'
import type { CommandCapability, DataState, StateSignalValue, SystemStatus, TelemetryPoint, UserRole } from '@/api/types'

const props = defineProps<{
  status: SystemStatus | null
  statusState: DataState
  capabilities: CommandCapability[]
  data: TelemetryPoint[]
  active: boolean
  role: UserRole
}>()

type Section = 'events' | 'signals' | 'trends' | 'system' | 'admin'
const section = ref<Section>('events')
const sections = computed(() => [
  { key: 'events' as const, label: 'Event history', icon: FileClock },
  { key: 'signals' as const, label: 'Signal diagnostics', icon: Activity },
  { key: 'trends' as const, label: 'Detailed trends', icon: ChartNoAxesCombined },
  { key: 'system' as const, label: 'Backend & capabilities', icon: Network },
  ...(props.role === 'admin' ? [{ key: 'admin' as const, label: 'Administration', icon: Users }] : [])
])
watch(() => props.role, (role) => { if (role !== 'admin' && section.value === 'admin') section.value = 'events' })

const signals = computed(() => {
  const unique = new Map<string, StateSignalValue>()
  if (!props.status) return []
  const values = [
    ...Object.values(props.status.cps.signals),
    ...Object.values(props.status.aps.signals),
    ...props.status.interlocks.map((item) => item.signal),
    ...props.status.alarms.signals
  ]
  values.forEach((signal) => unique.set(signal.logical_name, signal))
  return [...unique.values()].sort((a, b) => a.group.localeCompare(b.group) || a.display_name.localeCompare(b.display_name))
})

function raw(value: boolean | number | null) {
  return value === null ? '—' : String(value)
}
</script>

<template>
  <div class="space-y-3">
    <nav class="flex items-center gap-1 rounded-lg border bg-white p-1 shadow-sm">
      <button
        v-for="item in sections"
        :key="item.key"
        :class="['flex items-center gap-2 rounded px-3 py-2 text-xs font-semibold', section === item.key ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100']"
        @click="section = item.key"
      >
        <component :is="item.icon" class="size-4" /> {{ item.label }}
      </button>
    </nav>

    <LogsView v-if="section === 'events'" :active="active" />

    <section v-else-if="section === 'signals'" class="rounded-lg border bg-white shadow-sm">
      <div class="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h2 class="text-sm font-bold text-slate-800">Signal diagnostics</h2>
          <p class="text-[11px] text-slate-400">Raw and interpreted backend-observed machine-state signals</p>
        </div>
        <StatusPill :state="status?.coverage.complete ? 'ok' : 'warning'" :label="status?.coverage.complete ? 'COVERAGE COMPLETE' : 'COVERAGE INCOMPLETE'" />
      </div>
      <div class="max-h-[68vh] overflow-auto">
        <table class="w-full text-left text-[11px]">
          <thead class="sticky top-0 bg-slate-100 text-[9px] uppercase tracking-wide text-slate-500">
            <tr><th class="px-3 py-2">Group / signal</th><th class="px-3 py-2">Raw</th><th class="px-3 py-2">Interpreted</th><th class="px-3 py-2">Quality</th><th class="px-3 py-2">Data</th><th class="px-3 py-2">Mapped</th><th class="px-3 py-2">Source timestamp</th><th class="px-3 py-2">Observed</th></tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="signal in signals" :key="signal.logical_name" class="hover:bg-slate-50">
              <td class="px-3 py-2"><div class="font-semibold text-slate-700">{{ signal.display_name }}</div><div class="text-[9px] text-slate-400">{{ signal.group }} · {{ signal.logical_name }}</div></td>
              <td class="px-3 py-2 font-mono">{{ raw(signal.raw_value) }}</td>
              <td class="px-3 py-2"><StatusPill :state="signal.interpreted_state" :label="stateLabel(signal.interpreted_state)" /></td>
              <td class="px-3 py-2"><StatusPill :state="signal.quality" :label="stateLabel(signal.quality)" /></td>
              <td class="px-3 py-2"><StatusPill :state="signal.data_state" :label="stateLabel(signal.data_state)" /></td>
              <td class="px-3 py-2">{{ signal.mapped ? 'Yes' : 'No' }}</td>
              <td class="px-3 py-2 whitespace-nowrap text-slate-500">{{ formatTimestamp(signal.source_timestamp) }}</td>
              <td class="px-3 py-2 whitespace-nowrap text-slate-500">{{ formatTimestamp(signal.observed_at) }}</td>
            </tr>
            <tr v-if="!signals.length"><td colspan="8" class="px-3 py-8 text-center text-slate-500">Signal diagnostics unavailable.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <TrendPanel v-else-if="section === 'trends'" :data="data" />

    <div v-else-if="section === 'system'" class="grid grid-cols-1 gap-3 xl:grid-cols-3">
      <section class="rounded-lg border bg-white shadow-sm">
        <div class="flex items-center gap-2 border-b px-3 py-2"><Database class="size-4" /><h2 class="text-xs font-bold uppercase tracking-wider">Backend / communication</h2></div>
        <dl class="divide-y px-3 text-xs">
          <div class="flex justify-between py-2"><dt class="text-slate-500">Mode</dt><dd><StatusPill :state="status?.mode" :label="stateLabel(status?.mode)" /></dd></div>
          <div class="flex justify-between py-2"><dt class="text-slate-500">Connection</dt><dd><StatusPill :state="status?.connection_state" :label="stateLabel(status?.connection_state)" /></dd></div>
          <div class="flex justify-between py-2"><dt class="text-slate-500">Data state</dt><dd><StatusPill :state="status?.data_state ?? statusState" :label="stateLabel(status?.data_state ?? statusState)" /></dd></div>
          <div class="flex justify-between py-2"><dt class="text-slate-500">Source</dt><dd>{{ stateLabel(status?.source) }}</dd></div>
          <div class="flex justify-between gap-3 py-2"><dt class="text-slate-500">Last successful read</dt><dd class="text-right">{{ formatTimestamp(status?.last_successful_read) }}</dd></div>
          <div class="flex justify-between gap-3 py-2"><dt class="text-slate-500">Last connection attempt</dt><dd class="text-right">{{ formatTimestamp(status?.last_connection_attempt) }}</dd></div>
          <div v-if="status?.monitor_error" class="py-2 text-red-700">{{ status.monitor_error }}</div>
        </dl>
      </section>

      <section class="rounded-lg border bg-white shadow-sm">
        <div class="flex items-center gap-2 border-b px-3 py-2"><Shield class="size-4" /><h2 class="text-xs font-bold uppercase tracking-wider">Mapping coverage</h2></div>
        <dl class="grid grid-cols-2 gap-3 p-3 text-xs">
          <div class="rounded bg-slate-50 p-3"><dt class="text-[10px] uppercase text-slate-400">Total</dt><dd class="mt-1 text-2xl font-bold">{{ status?.coverage.total ?? 0 }}</dd></div>
          <div class="rounded bg-slate-50 p-3"><dt class="text-[10px] uppercase text-slate-400">Mapped</dt><dd class="mt-1 text-2xl font-bold">{{ status?.coverage.mapped ?? 0 }}</dd></div>
          <div class="rounded bg-slate-50 p-3"><dt class="text-[10px] uppercase text-slate-400">Trustworthy</dt><dd class="mt-1 text-2xl font-bold">{{ status?.coverage.trustworthy ?? 0 }}</dd></div>
          <div class="rounded bg-slate-50 p-3"><dt class="text-[10px] uppercase text-slate-400">Complete</dt><dd class="mt-2"><StatusPill :state="status?.coverage.complete ? 'ok' : 'warning'" :label="status?.coverage.complete ? 'YES' : 'NO'" /></dd></div>
        </dl>
        <div v-if="status?.coverage.missing.length" class="border-t p-3"><div class="mb-1 text-[10px] font-bold uppercase text-slate-400">Missing</div><div class="flex flex-wrap gap-1"><span v-for="item in status.coverage.missing" :key="item" class="rounded bg-slate-100 px-2 py-1 text-[10px]">{{ item }}</span></div></div>
      </section>

      <section class="rounded-lg border bg-white shadow-sm xl:row-span-2">
        <div class="flex items-center gap-2 border-b px-3 py-2"><Shield class="size-4" /><h2 class="text-xs font-bold uppercase tracking-wider">Command capabilities</h2></div>
        <div class="max-h-[68vh] divide-y overflow-auto">
          <div v-for="capability in capabilities" :key="capability.command" class="p-3">
            <div class="flex items-center justify-between"><span class="text-xs font-semibold text-slate-700">{{ capability.command }}</span><StatusPill state="unavailable" label="UNAVAILABLE" /></div>
            <div class="mt-1 text-[10px] text-slate-500">Target: {{ capability.target }}</div>
            <ul class="mt-1 list-disc pl-4 text-[10px] text-slate-500"><li v-for="reason in capability.reasons" :key="reason">{{ reason }}</li></ul>
          </div>
          <div v-if="!capabilities.length" class="p-4 text-xs text-slate-500">Capabilities unavailable.</div>
        </div>
      </section>
    </div>

    <AdminView v-else-if="section === 'admin' && role === 'admin'" />
  </div>
</template>
