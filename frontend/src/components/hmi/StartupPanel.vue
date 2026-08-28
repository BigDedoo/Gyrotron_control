<script setup lang="ts">
import { ChevronDown, ClipboardCheck, RotateCcw } from 'lucide-vue-next'
import StatusPill from './StatusPill.vue'
import { stateLabel } from '@/lib/hmi'
import { useStartupStore } from '@/stores/startup'
import type { ConditionState, InterlockStatus, SystemStatus } from '@/api/types'

const props = defineProps<{ status: SystemStatus | null }>()
const store = useStartupStore()

function interlockState(items: InterlockStatus[]): ConditionState {
  if (!items.length) return 'unknown'
  if (items.some((item) => item.state === 'fault')) return 'fault'
  if (items.every((item) => item.state === 'ok' && item.signal.mapped && item.signal.quality === 'good' && item.signal.data_state === 'live')) return 'ok'
  return 'unknown'
}
function observed(key: string) {
  if (!props.status) return 'unknown'
  if (key === 'prechecks') return interlockState(props.status.interlocks.filter((item) => !/cryo|cool|water/i.test(`${item.group} ${item.name}`)))
  if (key === 'cooling') return interlockState(props.status.interlocks.filter((item) => /cryo|cool|water/i.test(`${item.group} ${item.name}`)))
  if (key === 'cps_ready') return props.status.cps.ready
  if (key === 'cps_power') return props.status.cps.state
  if (key === 'aps_ready') return props.status.aps.ready
  if (key === 'aps_power') return props.status.aps.state
  return props.status.overall_state
}
function focusTarget(id?: string) {
  if (!id) return
  const target = document.getElementById(id)
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  target.classList.add('ring-2', 'ring-blue-400', 'rounded')
  setTimeout(() => target.classList.remove('ring-2', 'ring-blue-400', 'rounded'), 1400)
}
</script>

<template>
  <details open class="group rounded-lg border bg-white shadow-sm">
    <summary class="flex cursor-pointer list-none items-center justify-between border-b px-3 py-2">
      <h2 class="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-700"><ClipboardCheck class="size-4" /> Startup guidance</h2>
      <ChevronDown class="size-4 text-slate-400 transition-transform group-open:rotate-180" />
    </summary>
    <div class="p-3">
      <div class="mb-2 grid grid-cols-[1.5rem_1fr_5rem_4rem] gap-2 text-[9px] font-bold uppercase text-slate-400">
        <span>#</span><span>Guidance step</span><span>Observed</span><span>Review</span>
      </div>
      <div class="divide-y rounded border">
        <button
          v-for="(step, index) in store.STARTUP_STEPS"
          :key="step.key"
          :class="['grid w-full grid-cols-[1.5rem_1fr_5rem_4rem] items-center gap-2 px-2 py-1.5 text-left', index === store.currentIndex ? 'bg-blue-50' : 'hover:bg-slate-50']"
          @click="store.currentIndex = index; focusTarget(step.targetId)"
        >
          <span class="text-[10px] font-bold text-slate-400">{{ index + 1 }}</span>
          <span class="truncate text-[11px] font-medium text-slate-700" :title="step.desc">{{ step.title }}</span>
          <StatusPill :state="observed(step.key)" :label="stateLabel(observed(step.key))" />
          <span :class="['text-[10px] font-semibold', store.isStepDone(step.key) ? 'text-emerald-700' : 'text-slate-400']">{{ store.isStepDone(step.key) ? 'REVIEWED' : 'PENDING' }}</span>
        </button>
      </div>
      <div v-if="store.currentStep" class="mt-2 flex items-center justify-between gap-3 rounded bg-slate-50 px-2 py-2">
        <div class="min-w-0">
          <div class="truncate text-[11px] font-semibold text-slate-700">{{ store.currentStep.desc }}</div>
          <div class="truncate text-[9px] text-slate-400">{{ store.currentStep.hint }}</div>
        </div>
        <div class="flex shrink-0 items-center gap-1">
          <button class="rounded border bg-white px-2 py-1 text-[10px]" :disabled="store.currentIndex === 0" @click="store.prev">Back</button>
          <button class="rounded border bg-white px-2 py-1 text-[10px] disabled:text-slate-300" :disabled="!store.canMarkDone()" @click="store.markDone">Mark reviewed</button>
          <button class="rounded border bg-white px-2 py-1 text-[10px]" :disabled="store.currentIndex === store.STARTUP_STEPS.length - 1" @click="store.next">Next</button>
          <button class="rounded p-1 text-slate-400 hover:text-slate-700" title="Reset guidance marks" @click="store.reset"><RotateCcw class="size-3" /></button>
        </div>
      </div>
      <p class="mt-2 text-[9px] text-amber-700">Review marks are operator guidance only; they neither prove PLC readiness nor execute commands.</p>
    </div>
  </details>
</template>
