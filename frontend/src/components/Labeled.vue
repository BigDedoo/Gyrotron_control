<script setup lang="ts">
defineProps<{ label: string }>()
</script>

<template>
  <div class="grid grid-cols-12 items-center gap-3">
    <div class="col-span-5 text-sm text-muted-foreground">{{ label }}</div>
    <div class="col-span-7"><slot /></div>
  </div>
</template>
