<script setup lang="ts">
import { computed } from 'vue'
import { LogOut, ShieldAlert, UserRound } from 'lucide-vue-next'
import StatusPill from './StatusPill.vue'
import { highestSeverity, stateLabel } from '@/lib/hmi'
import type { DataState, SessionUser, SystemStatus } from '@/api/types'

const props = defineProps<{
  user: SessionUser
  status: SystemStatus | null
  statusState: DataState
}>()
defineEmits<{ logout: [] }>()

const mode = computed(() => props.status?.mode ?? 'unknown')
const modeLabel = computed(() => mode.value === 'simulation' ? 'SIMULATION' : mode.value === 'opcua_readonly' ? 'PLC READ ONLY' : 'MODE UNKNOWN')
const alarmSeverity = computed(() => highestSeverity(props.status?.alarms.active.map((alarm) => alarm.severity) ?? []))
const alarmState = computed(() => {
  if (!props.status || props.status.alarms.monitoring_state === 'unavailable') return 'unknown'
  if (props.status.alarms.monitoring_state === 'active') return alarmSeverity.value ?? 'warning'
  if (props.status.alarms.monitoring_state === 'no_active' && props.status.coverage.complete) return 'no_active'
  return 'warning'
})
const alarmLabel = computed(() => {
  if (!props.status) return 'ALARMS UNKNOWN'
  if (props.status.alarms.monitoring_state === 'active') return `${props.status.alarms.active.length} ACTIVE · ${stateLabel(alarmSeverity.value)}`
  if (props.status.alarms.monitoring_state === 'no_active' && props.status.coverage.complete) return 'NO ACTIVE ALARMS'
  return 'ALARM STATE INCOMPLETE'
})
</script>

<template>
  <header class="sticky top-0 z-40 border-b border-slate-700 bg-slate-950 text-white shadow-sm">
    <div class="flex min-h-14 items-center gap-4 px-4">
      <div class="flex min-w-56 items-center gap-3">
        <div class="grid size-8 place-items-center rounded bg-white text-xs font-black text-slate-950">GT</div>
        <div class="leading-tight">
          <div class="text-sm font-semibold">Gyrotron Control</div>
          <div class="text-[10px] uppercase tracking-[0.18em] text-slate-400">Operator HMI</div>
        </div>
      </div>

      <div class="flex flex-1 flex-wrap items-center gap-2">
        <StatusPill :state="mode" :label="modeLabel" />
        <StatusPill :state="statusState" :label="`DATA ${stateLabel(statusState)}`" />
        <StatusPill :state="status?.connection_state" :label="`LINK ${stateLabel(status?.connection_state)}`" />
        <StatusPill :state="status?.overall_state" :label="`MACHINE ${stateLabel(status?.overall_state)}`" />
        <StatusPill :state="alarmState" :label="alarmLabel" />
      </div>

      <div class="ml-auto flex items-center gap-3 border-l border-slate-700 pl-4">
        <ShieldAlert v-if="alarmState === 'critical'" class="size-5 text-red-400" />
        <UserRound class="size-4 text-slate-400" />
        <div class="text-right leading-tight">
          <div class="text-xs font-medium">{{ user.username }}</div>
          <div class="text-[10px] uppercase text-slate-400">{{ user.role }}</div>
        </div>
        <button class="rounded p-2 text-slate-400 hover:bg-slate-800 hover:text-white" title="Sign out" @click="$emit('logout')">
          <LogOut class="size-4" />
        </button>
      </div>
    </div>
  </header>
</template>
