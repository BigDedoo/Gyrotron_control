<script setup lang="ts">
defineProps<{ ok: boolean }>()
</script>

<template>
  <span
    :class="[
      'inline-block size-3 rounded-full mr-2',
      ok
        ? 'bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.25)]'
        : 'bg-red-500 shadow-[0_0_0_3px_rgba(239,68,68,0.25)]'
    ]"
  />
</template>
