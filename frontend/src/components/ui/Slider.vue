<script setup lang="ts">
import { SliderRoot, SliderTrack, SliderRange, SliderThumb } from 'radix-vue'
import { cn } from '@/lib/utils'
import { computed } from 'vue'

const props = defineProps<{
  modelValue?: number[]
  defaultValue?: number[]
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  class?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number[]): void
}>()

const localValue = computed({
  get: () => props.modelValue || props.defaultValue || [0],
  set: (val) => emit('update:modelValue', val)
})
</script>

<template>
  <SliderRoot
    v-model="localValue"
    :min="min"
    :max="max"
    :step="step"
    :disabled="disabled"
    :class="cn('relative flex w-full touch-none select-none items-center', $props.class)"
  >
    <SliderTrack class="relative h-2 w-full grow overflow-hidden rounded-full bg-secondary">
      <SliderRange class="absolute h-full bg-primary" />
    </SliderTrack>
    <SliderThumb
      v-for="(_, index) in localValue"
      :key="index"
      class="block h-5 w-5 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
    />
  </SliderRoot>
</template>
