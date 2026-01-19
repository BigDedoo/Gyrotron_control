<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardHeader, CardTitle, CardContent, Button } from '@/components/ui'
import { type Step } from '@/types'

const props = defineProps<{
  goTo: (tab: string, id?: string) => void
}>()

const STARTUP_STEPS: Step[] = [
  { key: "prechecks", title: "Pre-checks", desc: "Verify doors closed, waterflow OK, vacuum good, interlocks reset.", targetTab: "safety", hint: "5052: GS Doors, Waterflow, Poor vacuum, External interlock" },
  { key: "ipsp", title: "Ion pump ON", desc: "Ensure ion pump supply is powered.", targetTab: "monitoring", hint: "5017: Ion Pump V/I rising; 5052: IPPS ON" },
  { key: "heater", title: "Heaters ON", desc: "Turn on cathode filament/heater and wait for emission temperature.", targetTab: "monitoring", hint: "5017: Heater V/I; 5013: T hot/cold" },
  { key: "cps_rect", title: "CPS Rectifier ON", desc: "Enable CPS Power Rectifier.", targetTab: "power", targetId: "cps-rectifier", hint: "5068: DO0; 5052: CPS Rectifier ON" },
  { key: "cps_conv", title: "CPS Charging Converter ON", desc: "Enable CPS converter.", targetTab: "power", targetId: "cps-converter", hint: "5068: DO2; 5052: CPS Converter ON" },
  { key: "set_cath", title: "Set Cathode Voltage", desc: "Adjust cathode setpoint (AO1).", targetTab: "power", targetId: "setpoint-cathode", hint: "5024: AO1 Cathode preset" },
  { key: "set_an", title: "Set Anode Voltage", desc: "Adjust anode setpoint (AO2).", targetTab: "power", targetId: "setpoint-anode", hint: "5024: AO2 Anode preset" },
  { key: "set_pulse", title: "Set Pulse Duration", desc: "Adjust pulse duration (AO0).", targetTab: "power", targetId: "setpoint-pulse", hint: "5024: AO0 Pulse duration" },
  { key: "apply", title: "Apply Setpoints", desc: "Apply analog setpoints.", targetTab: "power", targetId: "apply-setpoints", hint: "UI: Apply setpoints button" },
  { key: "aps_rect", title: "APS Rectifier ON", desc: "Enable APS Power Rectifier.", targetTab: "power", targetId: "aps-rectifier", hint: "5069: DO0; 5052: APS Rectifier ON" },
  { key: "aps_conv", title: "APS Charging Converter ON", desc: "Enable APS converter.", targetTab: "power", targetId: "aps-converter", hint: "5069: DO2; 5052: APS Converter ON" },
  { key: "verify", title: "Verify Ready", desc: "Confirm CPS/APS Ready, no alarms, then proceed to operation.", targetTab: "dashboard", hint: "5052: Ready flags; Alarms clear" },
]

const currentIndex = ref(0)
const done = ref<Record<string, boolean>>({})

function step() {
  return STARTUP_STEPS[currentIndex.value]
}

function focusTarget() {
  props.goTo(step().targetTab || "dashboard", step().targetId)
}

function markDone() {
  done.value[step().key] = true
}

function canNext() {
  return done.value[step().key] || currentIndex.value === STARTUP_STEPS.length - 1
}

function canMarkDone() {
  if (currentIndex.value === 0) return true
  return done.value[STARTUP_STEPS[currentIndex.value - 1].key]
}
</script>

<template>
  <Card class="rounded-2xl">
    <CardHeader class="pb-2"><CardTitle class="text-base">Startup Sequencer</CardTitle></CardHeader>
    <CardContent>
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div class="lg:col-span-1 space-y-2">
          <div
            v-for="(s, idx) in STARTUP_STEPS"
            :key="s.key"
            :class="['px-3 py-2 rounded-xl border text-sm cursor-pointer', idx === currentIndex ? 'bg-slate-100 border-slate-300' : 'hover:bg-slate-50']"
            @click="currentIndex = idx"
          >
            <div class="flex items-center justify-between">
              <div class="font-medium">{{ idx + 1 }}. {{ s.title }}</div>
              <span v-if="done[s.key]" class="text-emerald-600 text-xs">✔</span>
            </div>
            <div class="text-muted-foreground text-xs">{{ s.desc }}</div>
            <div v-if="s.hint" class="text-[10px] text-slate-500 mt-1">Hint: {{ s.hint }}</div>
          </div>
        </div>
        
        <div class="lg:col-span-3">
          <div class="p-4 rounded-xl border bg-white space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-sm uppercase tracking-wide text-muted-foreground">Step {{ currentIndex + 1 }} of {{ STARTUP_STEPS.length }}</div>
                <div class="text-xl font-semibold">{{ step().title }}</div>
              </div>
              <div class="flex gap-2">
                <Button variant="outline" @click="focusTarget">Go to control</Button>
                <Button variant="secondary" @click="markDone" :disabled="!canMarkDone()">Mark done</Button>
              </div>
            </div>
            <p class="text-sm text-slate-600">{{ step().desc }}</p>
            <div v-if="step().hint" class="text-xs text-slate-500">Signals involved: {{ step().hint }}</div>
            <div class="pt-2 flex gap-2">
              <Button :disabled="currentIndex === 0" @click="currentIndex--" variant="ghost">Back</Button>
              <Button :disabled="!canNext()" @click="currentIndex = Math.min(currentIndex + 1, STARTUP_STEPS.length - 1)">Next</Button>
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
