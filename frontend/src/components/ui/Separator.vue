<script setup lang="ts">
import { Separator } from 'radix-vue'
import { cn } from '@/lib/utils'

defineProps<{
  orientation?: 'horizontal' | 'vertical'
  decorative?: boolean
  class?: string
}>()
</script>

<template>
  <Separator
    :orientation="orientation"
    :decorative="decorative"
    :class="
      cn(
        'shrink-0 bg-border',
        orientation === 'vertical' ? 'h-full w-[1px]' : 'h-[1px] w-full',
        $props.class
      )
    "
  />
</template>
