<script setup lang="ts">
import StatusPill from './StatusPill.vue'
import { stateLabel } from '@/lib/hmi'

defineProps<{
  label: string
  value?: string
  state?: string | null
  title?: string
  muted?: boolean
}>()
</script>

<template>
  <div :title="title" class="flex min-h-7 items-center justify-between gap-3 border-b border-slate-100 last:border-0">
    <span class="truncate text-[11px] text-slate-500">{{ label }}</span>
    <StatusPill v-if="state !== undefined" :state="state" :label="value ?? stateLabel(state)" />
    <span v-else :class="['text-right text-xs font-semibold tabular-nums', muted ? 'text-slate-400' : 'text-slate-800']">{{ value ?? '—' }}</span>
  </div>
</template>
