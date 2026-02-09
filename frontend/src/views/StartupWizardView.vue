<script setup lang="ts">
import { useStartupStore } from '@/stores/startup'

const props = defineProps<{
  goTo: (tab: string, id?: string) => void
}>()

const store = useStartupStore()

function focusTarget() {
  if (!store.currentStep) return
  props.goTo(store.currentStep.targetTab || 'dashboard', store.currentStep.targetId)
}
</script>

<template>
  <Card class="rounded-2xl">
    <CardHeader class="pb-2"><CardTitle class="text-base">Startup Sequencer</CardTitle></CardHeader>
    <CardContent>
      <div v-if="store.currentStep" class="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div class="lg:col-span-1 space-y-2">
          <div
            v-for="(s, idx) in store.STARTUP_STEPS"
            :key="s.key"
            :class="[
              'px-3 py-2 rounded-xl border text-sm cursor-pointer',
              idx === store.currentIndex ? 'bg-slate-100 border-slate-300' : 'hover:bg-slate-50'
            ]"
            @click="store.currentIndex = idx"
          >
            <div class="flex items-center justify-between">
              <div class="font-medium">{{ idx + 1 }}. {{ s.title }}</div>
              <span v-if="store.isStepDone(s.key)" class="text-emerald-600 text-xs">✔</span>
            </div>
            <div class="text-muted-foreground text-xs">{{ s.desc }}</div>
            <div v-if="s.hint" class="text-[10px] text-slate-500 mt-1">Hint: {{ s.hint }}</div>
          </div>
        </div>

        <div class="lg:col-span-3">
          <div class="p-4 rounded-xl border bg-white space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-sm uppercase tracking-wide text-muted-foreground">
                  Step {{ store.currentIndex + 1 }} of {{ store.STARTUP_STEPS.length }}
                </div>
                <div class="text-xl font-semibold">{{ store.currentStep.title }}</div>
              </div>
              <div class="flex gap-2">
                <Button variant="outline" @click="focusTarget">Go to control</Button>
                <Button variant="secondary" @click="store.markDone" :disabled="!store.canMarkDone()"
                  >Mark done</Button
                >
              </div>
            </div>
            <p class="text-sm text-slate-600">{{ store.currentStep.desc }}</p>
            <div v-if="store.currentStep.hint" class="text-xs text-slate-500">
              Signals involved: {{ store.currentStep.hint }}
            </div>
            <div class="pt-2 flex gap-2">
              <Button :disabled="store.currentIndex === 0" @click="store.prev" variant="ghost"
                >Back</Button
              >
              <Button
                :disabled="store.currentIndex === store.STARTUP_STEPS.length - 1"
                @click="store.next"
                >Next</Button
              >
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
