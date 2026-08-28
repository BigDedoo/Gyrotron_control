<script setup lang="ts">
import { computed } from 'vue'
import StatusPill from './StatusPill.vue'
import { hmiTone, stateLabel } from '@/lib/hmi'

const props = defineProps<{
  title: string
  subtitle?: string
  state?: string | null
  statusLabel?: string
}>()

const tone = computed(() => hmiTone(props.state))
const frame = computed(() => ({
  danger: 'border-red-400 ring-2 ring-red-100',
  warning: 'border-amber-300',
  healthy: 'border-slate-300',
  info: 'border-blue-300',
  neutral: 'border-slate-300'
})[tone.value])
</script>

<template>
  <section :class="['flex min-h-40 flex-col rounded border bg-white shadow-sm transition-shadow', frame]">
    <header class="flex items-start justify-between gap-2 border-b bg-slate-50/70 px-3 py-2">
      <div class="min-w-0">
        <h2 class="truncate text-sm font-black tracking-[0.08em] text-slate-800">{{ title }}</h2>
        <p v-if="subtitle" class="truncate text-[9px] uppercase tracking-wide text-slate-400">{{ subtitle }}</p>
      </div>
      <StatusPill :state="state" :label="statusLabel ?? stateLabel(state)" />
    </header>
    <div class="flex-1 px-3 py-2"><slot /></div>
    <footer v-if="$slots.controls" class="border-t bg-slate-50/60 px-3 py-2"><slot name="controls" /></footer>
  </section>
</template>
