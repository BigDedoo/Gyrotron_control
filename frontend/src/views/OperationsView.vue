<script setup lang="ts">
import { computed, ref } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
import EquipmentPanel from '@/components/hmi/EquipmentPanel.vue'
import EquipmentRow from '@/components/hmi/EquipmentRow.vue'
import RecentEvents from '@/components/hmi/RecentEvents.vue'
import StatusPill from '@/components/hmi/StatusPill.vue'
import { formatSignal, formatTimestamp, stateLabel } from '@/lib/hmi'
import type {
  CommandCapability,
  EquipmentStatus,
  InterlockStatus,
  LogicalCommand,
  StateSignalValue,
  SystemStatus
} from '@/api/types'

const props = defineProps<{
  status: SystemStatus | null
  capabilities: CommandCapability[]
  active: boolean
}>()
defineEmits<{ diagnostics: [] }>()

const cmpsCurrentDraft = ref('')
const cfpsPowerDraft = ref('')
const ahvpsVoltageDraft = ref('')
const chvpsVoltageDraft = ref('')
const pulseLengthDraft = ref('')
const pulsePeriodDraft = ref('')

const disabledControl = [
  'rounded border border-slate-200 bg-slate-100 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-slate-400',
  'cursor-not-allowed'
]

function interlock(logicalName: string) {
  return props.status?.interlocks.find((item) => item.logical_name === logicalName) ?? null
}
function alarm(logicalName: string) {
  return props.status?.alarms.signals.find((item) => item.logical_name === logicalName) ?? null
}
function equipment(key: string) {
  return props.status?.equipment[key] ?? null
}
function equipmentDataState(item: EquipmentStatus | null) {
  return item?.data_state ?? props.status?.data_state ?? 'unavailable'
}
function equipmentState(key: string, fallback = 'unknown') {
  const item = equipment(key)
  if (!item) return fallback
  if (item.state === 'fault' || item.state === 'active') return item.state
  const dataState = equipmentDataState(item)
  if (dataState !== 'live') return dataState
  return item.quality === 'good' ? item.state : item.quality
}
function equipmentConditionState(
  key: string,
  field: 'feedback' | 'interlock' | 'protection'
) {
  const item = equipment(key)
  const condition = item?.[field]
  if (condition === 'fault') return condition
  if (!item) return 'unknown'
  const dataState = equipmentDataState(item)
  if (dataState !== 'live') return dataState
  return item.quality === 'good' ? condition ?? 'unknown' : item.quality
}
function readingMuted(item: EquipmentStatus | null, reading: string) {
  const value = item?.readings[reading]
  return !value || value.quality !== 'good' || equipmentDataState(item) !== 'live'
}
function readingTitle(item: EquipmentStatus | null, reading: string) {
  const value = item?.readings[reading]
  return `Data ${equipmentDataState(item)} · quality ${value?.quality ?? 'unavailable'}`
}
function trustedSignalState(signal: StateSignalValue | null | undefined) {
  if (!signal) return 'unknown'
  if (!signal.mapped) return 'unmapped'
  if (signal.interpreted_state === 'fault' || signal.interpreted_state === 'active') return signal.interpreted_state
  if (signal.quality === 'bad' || signal.quality === 'unavailable') return signal.quality
  if (signal.data_state === 'stale' || signal.data_state === 'unavailable' || signal.data_state === 'degraded') return signal.data_state
  return signal.interpreted_state
}
function trustedInterlockState(item: InterlockStatus | null) {
  if (!item) return 'unknown'
  const signalState = trustedSignalState(item.signal)
  return ['bad', 'unavailable', 'unmapped', 'stale', 'degraded', 'unknown'].includes(signalState) ? signalState : item.state
}
function signalTitle(signal: StateSignalValue | null | undefined) {
  if (!signal) return 'No backend signal is available.'
  return `${signal.logical_name} · quality ${signal.quality} · ${signal.mapped ? 'mapped' : 'unmapped'} · observed ${formatTimestamp(signal.observed_at)}`
}
function capabilityReason(command: LogicalCommand) {
  const capability = props.capabilities.find((item) => item.command === command)
  return capability?.reasons[0] ?? capability?.blockers[0] ?? 'No commissioned backend command capability.'
}
function clearPulseDrafts() {
  pulseLengthDraft.value = ''
  pulsePeriodDraft.value = ''
}

const cmps = computed(() => interlock('interlock.cmps'))
const ipps = computed(() => interlock('interlock.ipps'))
const arcSignal = computed(() => alarm('alarm.arc_detector'))
const arcState = computed(() => {
  const state = trustedSignalState(arcSignal.value)
  if (state === 'active') return 'fault'
  if (state === 'inactive') return 'ok'
  return state
})
const arcLabel = computed(() => arcState.value === 'fault' ? 'ARC DETECTED' : arcState.value === 'ok' ? 'NO ARC' : stateLabel(arcState.value))
const hvpsState = computed(() => {
  const states = ['ahvps', 'chvps'].map((key) => equipmentState(key, 'unmapped'))
  if (states.includes('fault')) return 'fault'
  for (const state of ['unavailable', 'stale', 'degraded', 'bad', 'uncertain']) {
    if (states.includes(state)) return state
  }
  if (states.every((state) => state === 'on')) return 'on'
  if (states.every((state) => state === 'unmapped')) return 'unmapped'
  return 'unknown'
})
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between rounded border bg-white px-3 py-2 shadow-sm">
      <span class="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Equipment workspace</span>
      <span class="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-slate-500">Hardware commands unavailable</span>
    </div>

    <div class="grid grid-cols-1 items-start gap-3 md:grid-cols-2 xl:grid-cols-3">
      <div id="cmps-panel">
        <EquipmentPanel title="CMPS" subtitle="Current-controlled supply" :state="equipmentState('cmps', trustedInterlockState(cmps))" :status-label="stateLabel(equipmentState('cmps', trustedInterlockState(cmps)))">
          <EquipmentRow label="State" :state="equipmentState('cmps', trustedInterlockState(cmps))" />
          <EquipmentRow label="Current · Actual" :value="formatSignal(equipment('cmps')?.readings.current, 2)" :muted="readingMuted(equipment('cmps'), 'current')" :title="readingTitle(equipment('cmps'), 'current')" />
          <EquipmentRow label="Supply interlock" :state="trustedInterlockState(cmps)" :title="signalTitle(cmps?.signal)" />
          <template #controls>
            <div class="mb-1 text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">Commands</div>
            <div class="flex min-h-7 items-center justify-between gap-2">
              <label for="cmps-current-setpoint" class="text-[11px] font-medium text-slate-600">Current setpoint</label>
              <div class="flex items-center rounded border bg-white px-2"><input id="cmps-current-setpoint" v-model="cmpsCurrentDraft" type="number" min="0" step="0.01" class="h-6 w-20 text-right text-xs font-semibold tabular-nums outline-none" placeholder="—" /><span class="ml-1 text-[9px] text-slate-400">A</span></div>
            </div>
            <div class="mt-1"><span title="No CMPS current command exists in the backend contract."><button disabled :class="disabledControl">Apply unavailable</button></span></div>
          </template>
        </EquipmentPanel>
      </div>

      <div id="cfps-panel">
        <EquipmentPanel title="CFPS" subtitle="Power supply" :state="equipmentState('cfps', 'unmapped')" :status-label="stateLabel(equipmentState('cfps', 'unmapped'))">
          <EquipmentRow label="State" :state="equipmentState('cfps', 'unknown')" />
          <EquipmentRow label="Power · Actual" :value="formatSignal(equipment('cfps')?.readings.power, 1)" :muted="readingMuted(equipment('cfps'), 'power')" :title="readingTitle(equipment('cfps'), 'power')" />
          <EquipmentRow label="Feedback" :state="equipmentConditionState('cfps', 'feedback')" />
          <EquipmentRow label="Interlock" :state="equipmentConditionState('cfps', 'interlock')" />
          <template #controls>
            <div class="mb-1 text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">Commands</div>
            <div class="flex min-h-7 items-center justify-between gap-2">
              <label for="cfps-power-setpoint" class="text-[11px] font-medium text-slate-600">Power setpoint</label>
              <div class="flex items-center rounded border bg-white px-2"><input id="cfps-power-setpoint" v-model="cfpsPowerDraft" type="number" min="0" step="1" class="h-6 w-20 text-right text-xs font-semibold tabular-nums outline-none" placeholder="—" /><span class="ml-1 text-[9px] text-slate-400">W</span></div>
            </div>
            <div class="mt-1"><span title="No CFPS power command exists in the backend contract."><button disabled :class="disabledControl">Apply unavailable</button></span></div>
          </template>
        </EquipmentPanel>
      </div>

      <div id="ipps-panel">
        <EquipmentPanel title="IPPS" subtitle="Ion pump power supply" :state="equipmentState('ipps', trustedInterlockState(ipps))" :status-label="stateLabel(equipmentState('ipps', trustedInterlockState(ipps)))">
          <EquipmentRow label="State" :state="equipmentState('ipps', trustedInterlockState(ipps))" />
          <EquipmentRow label="Ion pump voltage" :value="formatSignal(equipment('ipps')?.readings.voltage)" :muted="readingMuted(equipment('ipps'), 'voltage')" :title="readingTitle(equipment('ipps'), 'voltage')" />
          <EquipmentRow label="Ion pump current" :value="formatSignal(equipment('ipps')?.readings.current, 2)" :muted="readingMuted(equipment('ipps'), 'current')" :title="readingTitle(equipment('ipps'), 'current')" />
          <EquipmentRow label="Supply interlock" :state="trustedInterlockState(ipps)" :title="signalTitle(ipps?.signal)" />
        </EquipmentPanel>
      </div>

      <div id="arc-detector-panel">
        <EquipmentPanel title="ARC DETECTOR" subtitle="Arc alarm" :state="arcState" :status-label="arcLabel">
          <EquipmentRow label="Detector state" :state="arcState" :value="arcLabel" :title="signalTitle(arcSignal)" />
          <EquipmentRow label="Severity" :value="arcSignal?.severity?.toUpperCase() ?? 'UNAVAILABLE'" :muted="!arcSignal?.severity" />
          <EquipmentRow v-if="!arcSignal || arcSignal.quality !== 'good'" label="Data quality" :value="arcSignal?.quality?.toUpperCase() ?? 'UNAVAILABLE'" muted />
        </EquipmentPanel>
      </div>

      <div id="hvps-panel">
        <EquipmentPanel title="HVPS" subtitle="Accelerator and collector supplies" :state="hvpsState" :status-label="stateLabel(hvpsState)">
          <div class="grid grid-cols-1 gap-2 xl:grid-cols-2">
          <section class="w-full overflow-hidden rounded border border-slate-200 bg-slate-50/50">
            <div class="px-2 py-1.5">
              <div class="mb-1 flex items-center justify-between border-b border-slate-200 pb-1">
                <h3 class="text-[11px] font-black tracking-[0.08em] text-slate-700">AHVPS</h3>
                <StatusPill :state="equipmentState('ahvps', 'unmapped')" />
              </div>
              <EquipmentRow label="State" :state="equipmentState('ahvps', 'unknown')" />
              <EquipmentRow label="Voltage · Actual" :value="formatSignal(equipment('ahvps')?.readings.voltage, 2)" :muted="readingMuted(equipment('ahvps'), 'voltage')" :title="readingTitle(equipment('ahvps'), 'voltage')" />
              <EquipmentRow label="Protection" :state="equipmentConditionState('ahvps', 'protection')" />
              <EquipmentRow label="Interlock" :state="equipmentConditionState('ahvps', 'interlock')" />
            </div>
            <div class="border-t border-slate-200 bg-slate-100/70 px-2 py-1.5">
              <div class="mb-1 text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">Commands</div>
              <div class="flex items-center justify-between gap-2"><label for="ahvps-voltage-setpoint" class="text-[10px] font-bold text-slate-600">Voltage setpoint</label><div class="flex items-center rounded border bg-white px-2"><input id="ahvps-voltage-setpoint" v-model="ahvpsVoltageDraft" type="number" min="0" step="0.1" class="h-6 w-16 text-right text-xs font-semibold tabular-nums outline-none" placeholder="—" /><span class="ml-1 text-[9px] text-slate-400">kV</span></div></div>
              <div class="mt-1"><span title="No AHVPS voltage command mapping exists in the backend contract."><button disabled :class="disabledControl">Apply unavailable</button></span></div>
            </div>
          </section>
          <section class="w-full overflow-hidden rounded border border-slate-300 bg-slate-50/50">
            <div class="px-2 py-1.5">
              <div class="mb-1 flex items-center justify-between border-b border-slate-200 pb-1">
                <h3 class="text-[11px] font-black tracking-[0.08em] text-slate-700">CHVPS</h3>
                <StatusPill :state="equipmentState('chvps', 'unmapped')" />
              </div>
              <EquipmentRow label="State" :state="equipmentState('chvps', 'unknown')" />
              <EquipmentRow label="Voltage · Actual" :value="formatSignal(equipment('chvps')?.readings.voltage, 2)" :muted="readingMuted(equipment('chvps'), 'voltage')" :title="readingTitle(equipment('chvps'), 'voltage')" />
              <EquipmentRow label="Protection" :state="equipmentConditionState('chvps', 'protection')" />
              <EquipmentRow label="Interlock" :state="equipmentConditionState('chvps', 'interlock')" />
            </div>
            <div class="border-t border-slate-200 bg-slate-100/70 px-2 py-1.5">
              <div class="mb-1 text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">Commands</div>
              <div class="flex items-center justify-between gap-2"><label for="chvps-voltage-setpoint" class="text-[10px] font-bold text-slate-600">Voltage setpoint</label><div class="flex items-center rounded border bg-white px-2"><input id="chvps-voltage-setpoint" v-model="chvpsVoltageDraft" type="number" min="0" step="0.1" class="h-6 w-16 text-right text-xs font-semibold tabular-nums outline-none" placeholder="—" /><span class="ml-1 text-[9px] text-slate-400">kV</span></div></div>
              <div class="mt-1"><span title="No CHVPS voltage command mapping exists in the backend contract."><button disabled :class="disabledControl">Apply unavailable</button></span></div>
            </div>
          </section>
          </div>
        </EquipmentPanel>
      </div>

      <div id="pulse-generator-panel">
        <EquipmentPanel title="PULSE GENERATOR" subtitle="Pulse timing" :state="equipmentState('pulse_generator', 'unmapped')" :status-label="stateLabel(equipmentState('pulse_generator', 'unmapped'))">
          <EquipmentRow label="State" :state="equipmentState('pulse_generator', 'unknown')" />
          <EquipmentRow label="Length · Actual" :value="formatSignal(equipment('pulse_generator')?.readings.pulse_length, 3)" :muted="readingMuted(equipment('pulse_generator'), 'pulse_length')" :title="readingTitle(equipment('pulse_generator'), 'pulse_length')" />
          <EquipmentRow label="Period · Actual" :value="formatSignal(equipment('pulse_generator')?.readings.pulse_period, 3)" :muted="readingMuted(equipment('pulse_generator'), 'pulse_period')" :title="readingTitle(equipment('pulse_generator'), 'pulse_period')" />
          <template #controls>
            <div class="mb-1 text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">Commands</div>
            <div class="flex min-h-7 items-center justify-between gap-2">
              <label for="pulse-length-setpoint" class="text-[11px] font-medium text-slate-600">Pulse length</label>
              <div class="flex items-center rounded border bg-white px-2"><input id="pulse-length-setpoint" v-model="pulseLengthDraft" type="number" min="0" step="0.01" class="h-6 w-20 text-right text-xs font-semibold tabular-nums outline-none" placeholder="—" /><span class="ml-1 text-[9px] text-slate-400">ms</span></div>
            </div>
            <div class="flex min-h-7 items-center justify-between gap-2">
              <label for="pulse-period-setpoint" class="text-[11px] font-medium text-slate-600">Pulse period</label>
              <div class="flex items-center rounded border bg-white px-2"><input id="pulse-period-setpoint" v-model="pulsePeriodDraft" type="number" min="0" step="0.01" class="h-6 w-20 text-right text-xs font-semibold tabular-nums outline-none" placeholder="—" /><span class="ml-1 text-[9px] text-slate-400">s</span></div>
            </div>
            <div class="mt-1 flex items-center gap-2"><span :title="capabilityReason('setpoint.apply')"><button disabled :class="disabledControl">Apply unavailable</button></span><button class="rounded p-1 text-slate-400 hover:text-slate-700" title="Clear local display drafts" @click="clearPulseDrafts"><RotateCcw class="size-3" /></button></div>
          </template>
        </EquipmentPanel>
      </div>
    </div>

    <RecentEvents :active="active" @history="$emit('diagnostics')" />
  </div>
</template>
