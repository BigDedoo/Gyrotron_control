import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { type Step } from '@/types'

// Define steps definition here or import constant if shared
export const STARTUP_STEPS: Step[] = [
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

export const useStartupStore = defineStore('startup', () => {
    const currentIndex = ref(0)
    const done = ref<Record<string, boolean>>({})

    const currentStep = computed(() => STARTUP_STEPS[currentIndex.value])

    function markDone() {
        if (!currentStep.value) return
        done.value[currentStep.value.key] = true
    }

    function canMarkDone() {
        if (currentIndex.value === 0) return true
        const prevStep = STARTUP_STEPS[currentIndex.value - 1]
        return prevStep && done.value[prevStep.key]
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
        return done.value[key]
    }

    return {
        currentIndex,
        currentStep,
        STARTUP_STEPS,
        markDone,
        canMarkDone,
        next,
        prev,
        reset,
        isStepDone
    }
})
