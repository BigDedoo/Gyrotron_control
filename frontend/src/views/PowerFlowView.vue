<script setup lang="ts">
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui'
</script>

<template>
  <Card class="rounded-2xl">
    <CardHeader class="pb-2"><CardTitle class="text-base">Power Flow</CardTitle></CardHeader>
    <CardContent>
      <div class="w-full overflow-hidden rounded-xl border bg-white">
        <img
          src="/power_flow.png"
          alt="Gyrotron Control Architecture Power Flow"
          class="max-w-full max-h-[75vh] mx-auto object-contain"
        />
      </div>
    </CardContent>
  </Card>
</template>
