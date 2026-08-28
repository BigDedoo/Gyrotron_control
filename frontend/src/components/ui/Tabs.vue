<script setup lang="ts">
import { TabsRoot as Root } from 'radix-vue'
import { cn } from '@/lib/utils'

defineProps<{
  defaultValue?: string
  modelValue?: string
  class?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>

<template>
  <Root
    :default-value="defaultValue"
    :model-value="modelValue"
    @update:modelValue="emit('update:modelValue', $event)"
    :class="cn($props.class)"
  >
    <slot />
  </Root>
</template>
