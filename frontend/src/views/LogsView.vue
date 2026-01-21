<script setup lang="ts">
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui'

const rows = [
  { t: "12:02:41", m: "CPS Rectifier ON" },
  { t: "12:03:02", m: "CPS Converter ON" },
  { t: "12:03:15", m: "Apply setpoints (2.5ms / 6.0V / 5.0V)" },
  { t: "12:07:11", m: "ARC detected on APS – protection active" },
]
</script>

<template>
  <Card class="rounded-2xl">
    <CardHeader class="pb-2"><CardTitle class="text-base">Event Log (mock)</CardTitle></CardHeader>
    <CardContent>
      <div class="grid grid-cols-12 text-xs uppercase text-muted-foreground mb-2">
        <div class="col-span-2">Time</div>
        <div class="col-span-10">Message</div>
      </div>
      <div class="space-y-2">
        <div v-for="(r, i) in rows" :key="i" class="grid grid-cols-12 items-center text-sm bg-muted/30 rounded-xl px-3 py-2">
          <div class="col-span-2 font-mono">{{ r.t }}</div>
          <div class="col-span-10">{{ r.m }}</div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
