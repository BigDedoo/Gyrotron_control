import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Step } from '@/types'

export const STARTUP_STEPS: Step[] = [
  { key: 'prechecks', title: 'Vacuum / environment', desc: 'Review environmental and vacuum interlocks.', targetId: 'environment-panel', hint: 'Backend-observed interlocks remain authoritative.' },
  { key: 'cooling', title: 'Cooling / cryogenics', desc: 'Review cooling and cryogenic indications.', targetId: 'cryogenics-panel', hint: 'Review waterflow, helium level, and temperatures.' },
  { key: 'cps_ready', title: 'CPS ready', desc: 'Confirm the backend-observed CPS ready state.', targetId: 'cps-panel', hint: 'This checklist does not change CPS state.' },
  { key: 'cps_power', title: 'CPS power', desc: 'Review CPS rectifier, converter, and protection state.', targetId: 'power-controls', hint: 'Write commands are unavailable.' },
  { key: 'aps_ready', title: 'APS ready', desc: 'Confirm the backend-observed APS ready state.', targetId: 'aps-panel', hint: 'This checklist does not change APS state.' },
  { key: 'aps_power', title: 'APS power', desc: 'Review APS rectifier, converter, and protection state.', targetId: 'power-controls', hint: 'Write commands are unavailable.' },
  { key: 'verify', title: 'Final verification', desc: 'Review overall state, alarms, and interlocks before operation.', targetId: 'machine-status', hint: 'Only backend-observed state can prove readiness.' }
]

export const useStartupStore = defineStore('startup', () => {
  const currentIndex = ref(0)
  const done = ref<Record<string, boolean>>({})
  const currentStep = computed(() => STARTUP_STEPS[currentIndex.value])

  function markDone() {
    if (currentStep.value) done.value[currentStep.value.key] = true
  }
  function canMarkDone() {
    if (currentIndex.value === 0) return true
    const previous = STARTUP_STEPS[currentIndex.value - 1]
    return Boolean(previous && done.value[previous.key])
  }
  function next() {
    currentIndex.value = Math.min(currentIndex.value + 1, STARTUP_STEPS.length - 1)
  }
  function prev() {
    currentIndex.value = Math.max(currentIndex.value - 1, 0)
  }
  function reset() {
    currentIndex.value = 0
    done.value = {}
  }
  function isStepDone(key: string) {
    return Boolean(done.value[key])
  }

  return { currentIndex, currentStep, STARTUP_STEPS, markDone, canMarkDone, next, prev, reset, isStepDone }
})
