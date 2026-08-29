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
  EquipmentStatusBase,
  LogicalCommand,
  SignalValue,
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

function equipmentState(item: EquipmentStatusBase | null | undefined, fallback = 'unknown') {
  if (!item) return fallback
  return trustedSignalState(item.state)
}
function equipmentConditionState(signal: StateSignalValue | null | undefined) {
  return trustedSignalState(signal)
}
function readingMuted(value: SignalValue | null | undefined) {
  return !value?.mapped || value.quality !== 'good' || props.status?.data_state !== 'live'
}
function readingTitle(value: SignalValue | null | undefined) {
  if (!value) return 'No backend readback is available.'
  return `${value.mapped ? 'Mapped' : 'Not mapped'} · quality ${value.quality} · source ${formatTimestamp(value.source_timestamp)} · observed ${formatTimestamp(value.observed_at)}`
}
function trustedSignalState(signal: StateSignalValue | null | undefined) {
  if (!signal) return 'unknown'
  if (!signal.mapped) return 'unmapped'
  if (signal.interpreted_state === 'fault' || signal.interpreted_state === 'active') return signal.interpreted_state
  if (signal.quality === 'bad' || signal.quality === 'unavailable') return signal.quality
  if (signal.data_state === 'stale' || signal.data_state === 'unavailable' || signal.data_state === 'degraded') return signal.data_state
  return signal.interpreted_state
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

const cmps = computed(() => props.status?.equipment.cmps)
const cfps = computed(() => props.status?.equipment.cfps)
const ipps = computed(() => props.status?.equipment.ipps)
const arcDetector = computed(() => props.status?.equipment.arc_detector)
const ahvps = computed(() => props.status?.equipment.hvps.ahvps)
const chvps = computed(() => props.status?.equipment.hvps.chvps)
const pulseGenerator = computed(() => props.status?.equipment.pulse_generator)
const arcState = computed(() => {
  const state = trustedSignalState(arcDetector.value?.state)
  if (state === 'active') return 'fault'
  if (state === 'inactive') return 'ok'
  return state
})
const arcLabel = computed(() => arcState.value === 'fault' ? 'ARC DETECTED' : arcState.value === 'ok' ? 'NO ARC' : stateLabel(arcState.value))
const hvpsState = computed(() => {
  const states = [equipmentState(ahvps.value, 'unmapped'), equipmentState(chvps.value, 'unmapped')]
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
        <EquipmentPanel title="CMPS" subtitle="Current-controlled supply" :state="equipmentState(cmps)" :status-label="stateLabel(equipmentState(cmps))">
          <EquipmentRow label="State" :state="equipmentState(cmps)" :title="signalTitle(cmps?.state)" />
          <EquipmentRow label="Current · Actual" :value="formatSignal(cmps?.current, 2)" :muted="readingMuted(cmps?.current)" :title="readingTitle(cmps?.current)" />
          <EquipmentRow label="Supply interlock" :state="equipmentConditionState(cmps?.interlock)" :title="signalTitle(cmps?.interlock)" />
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
        <EquipmentPanel title="CFPS" subtitle="Power supply" :state="equipmentState(cfps)" :status-label="stateLabel(equipmentState(cfps))">
          <EquipmentRow label="State" :state="equipmentState(cfps)" :title="signalTitle(cfps?.state)" />
          <EquipmentRow label="Power · Actual" :value="formatSignal(cfps?.power, 1)" :muted="readingMuted(cfps?.power)" :title="readingTitle(cfps?.power)" />
          <EquipmentRow label="Feedback" :state="equipmentConditionState(cfps?.feedback)" :title="signalTitle(cfps?.feedback)" />
          <EquipmentRow label="Interlock" :state="equipmentConditionState(cfps?.interlock)" :title="signalTitle(cfps?.interlock)" />
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
        <EquipmentPanel title="IPPS" subtitle="Ion pump power supply" :state="equipmentState(ipps)" :status-label="stateLabel(equipmentState(ipps))">
          <EquipmentRow label="State" :state="equipmentState(ipps)" :title="signalTitle(ipps?.state)" />
          <EquipmentRow label="Ion pump voltage" :value="formatSignal(ipps?.voltage)" :muted="readingMuted(ipps?.voltage)" :title="readingTitle(ipps?.voltage)" />
          <EquipmentRow label="Ion pump current" :value="formatSignal(ipps?.current, 2)" :muted="readingMuted(ipps?.current)" :title="readingTitle(ipps?.current)" />
          <EquipmentRow label="Supply interlock" :state="equipmentConditionState(ipps?.interlock)" :title="signalTitle(ipps?.interlock)" />
        </EquipmentPanel>
      </div>

      <div id="arc-detector-panel">
        <EquipmentPanel title="ARC DETECTOR" subtitle="Arc alarm" :state="arcState" :status-label="arcLabel">
          <EquipmentRow label="Detector state" :state="arcState" :value="arcLabel" :title="signalTitle(arcDetector?.state)" />
          <EquipmentRow label="Severity" :value="arcDetector?.severity?.toUpperCase() ?? 'UNAVAILABLE'" :muted="!arcDetector?.severity" />
          <EquipmentRow v-if="!arcDetector || arcDetector.state.quality !== 'good'" label="Data quality" :value="arcDetector?.state.quality?.toUpperCase() ?? 'UNAVAILABLE'" muted />
        </EquipmentPanel>
      </div>

      <div id="hvps-panel">
        <EquipmentPanel title="HVPS" subtitle="Accelerator and collector supplies" :state="hvpsState" :status-label="stateLabel(hvpsState)">
          <div class="grid grid-cols-1 gap-2 xl:grid-cols-2">
          <section class="w-full overflow-hidden rounded border border-slate-200 bg-slate-50/50">
            <div class="px-2 py-1.5">
              <div class="mb-1 flex items-center justify-between border-b border-slate-200 pb-1">
                <h3 class="text-[11px] font-black tracking-[0.08em] text-slate-700">AHVPS</h3>
                <StatusPill :state="equipmentState(ahvps, 'unmapped')" />
              </div>
              <EquipmentRow label="State" :state="equipmentState(ahvps)" :title="signalTitle(ahvps?.state)" />
              <EquipmentRow label="Voltage · Actual" :value="formatSignal(ahvps?.voltage, 2)" :muted="readingMuted(ahvps?.voltage)" :title="readingTitle(ahvps?.voltage)" />
              <EquipmentRow label="Protection" :state="equipmentConditionState(ahvps?.protection)" :title="signalTitle(ahvps?.protection)" />
              <EquipmentRow label="Interlock" :state="equipmentConditionState(ahvps?.interlock)" :title="signalTitle(ahvps?.interlock)" />
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
                <StatusPill :state="equipmentState(chvps, 'unmapped')" />
              </div>
              <EquipmentRow label="State" :state="equipmentState(chvps)" :title="signalTitle(chvps?.state)" />
              <EquipmentRow label="Voltage · Actual" :value="formatSignal(chvps?.voltage, 2)" :muted="readingMuted(chvps?.voltage)" :title="readingTitle(chvps?.voltage)" />
              <EquipmentRow label="Protection" :state="equipmentConditionState(chvps?.protection)" :title="signalTitle(chvps?.protection)" />
              <EquipmentRow label="Interlock" :state="equipmentConditionState(chvps?.interlock)" :title="signalTitle(chvps?.interlock)" />
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
        <EquipmentPanel title="PULSE GENERATOR" subtitle="Pulse timing" :state="equipmentState(pulseGenerator)" :status-label="stateLabel(equipmentState(pulseGenerator))">
          <EquipmentRow label="State" :state="equipmentState(pulseGenerator)" :title="signalTitle(pulseGenerator?.state)" />
          <EquipmentRow label="Length · Actual" :value="formatSignal(pulseGenerator?.pulse_length, 3)" :muted="readingMuted(pulseGenerator?.pulse_length)" :title="readingTitle(pulseGenerator?.pulse_length)" />
          <EquipmentRow label="Period · Actual" :value="formatSignal(pulseGenerator?.pulse_period, 3)" :muted="readingMuted(pulseGenerator?.pulse_period)" :title="readingTitle(pulseGenerator?.pulse_period)" />
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
