<script setup lang="ts">
const props = withDefaults(defineProps<{
  label: string
  ok: boolean
  warn?: boolean
}>(), {
  warn: false
})
</script>

<template>
  <div class="flex items-center gap-2 text-sm">
    <span 
      :class="[
        'inline-block size-2 rounded-full',
        ok ? 'bg-emerald-500' : warn ? 'bg-amber-500' : 'bg-red-500'
      ]"
    ></span>
    <span>{{ label }}</span>
  </div>
</template>
