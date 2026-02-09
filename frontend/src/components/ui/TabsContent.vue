<script setup lang="ts">
import { TabsContent as Content } from 'radix-vue'
import { cn } from '@/lib/utils'

defineProps<{
  value: string
  class?: string
}>()
</script>

<template>
  <Content
    :value="value"
    :class="
      cn(
        'mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        $props.class
      )
    "
  >
    <slot />
  </Content>
</template>
