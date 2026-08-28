<script setup lang="ts">
import { computed } from 'vue'
import { hmiTone, stateLabel } from '@/lib/hmi'

const props = defineProps<{
  state?: string | null
  label?: string
  title?: string
  dotOnly?: boolean
}>()

const tone = computed(() => hmiTone(props.state))
const classes = computed(() => ({
  healthy: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  danger: 'border-red-300 bg-red-50 text-red-800',
  warning: 'border-amber-300 bg-amber-50 text-amber-900',
  info: 'border-blue-200 bg-blue-50 text-blue-800',
  neutral: 'border-slate-300 bg-slate-100 text-slate-600'
})[tone.value])
const dotClass = computed(() => ({
  healthy: 'bg-emerald-500',
  danger: 'bg-red-600',
  warning: 'bg-amber-500',
  info: 'bg-blue-500',
  neutral: 'bg-slate-400'
})[tone.value])
</script>

<template>
  <span
    :title="title"
    :aria-label="label ?? stateLabel(state)"
    :class="[
      'inline-flex shrink-0 items-center border font-semibold tracking-wide',
      dotOnly ? 'size-3 justify-center rounded-full border-0' : 'gap-1.5 rounded px-2 py-0.5 text-[10px]',
      classes
    ]"
  >
    <span v-if="!dotOnly" :class="['size-1.5 rounded-full', dotClass]" />
    <span v-if="!dotOnly">{{ label ?? stateLabel(state) }}</span>
  </span>
</template>
