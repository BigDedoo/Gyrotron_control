<script setup lang="ts">
import { TabsList as List } from 'radix-vue'
import { cn } from '@/lib/utils'

defineProps<{ class?: string }>()
</script>

<template>
  <List
    :class="
      cn(
        'inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground',
        $props.class
      )
    "
  >
    <slot />
  </List>
</template>
