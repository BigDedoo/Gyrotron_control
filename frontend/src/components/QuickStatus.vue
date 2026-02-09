<script setup lang="ts">
import { Card, CardHeader, CardTitle, CardContent, Separator } from '@/components/ui'
import Indicator from '@/components/Indicator.vue'
import { ShieldCheck, AlertTriangle } from 'lucide-vue-next'

defineProps<{
  cpsOn: boolean
  apsOn: boolean
  faults: string[]
}>()
</script>

<template>
  <Card class="rounded-2xl">
    <CardHeader class="pb-2">
      <CardTitle class="text-base flex items-center gap-2">
        <ShieldCheck class="size-4" /> Quick Status
      </CardTitle>
    </CardHeader>
    <CardContent class="space-y-4">
      <div>
        <div class="font-medium mb-2">CPS</div>
        <div class="space-y-1">
          <Indicator label="Ready" :ok="cpsOn" />
          <Indicator label="Power Rectifier ON" :ok="cpsOn" />
          <Indicator label="Charging Converter ON" :ok="false" warn />
          <Indicator label="Protection" :ok="true" />
        </div>
      </div>
      <Separator />
      <div>
        <div class="font-medium mb-2">APS</div>
        <div class="space-y-1">
          <Indicator label="Ready" :ok="apsOn" />
          <Indicator label="Power Rectifier ON" :ok="apsOn" />
          <Indicator label="Charging Converter ON" :ok="false" warn />
          <Indicator label="Protection" :ok="true" />
        </div>
      </div>
      <Separator />
      <div>
        <div class="font-medium mb-2">Active Alarms</div>
        <div v-if="faults.length === 0">
          <span
            class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-emerald-600 text-primary-foreground hover:bg-emerald-600/80"
            >None</span
          >
        </div>
        <ul v-else class="text-sm list-disc ml-5 space-y-1">
          <li v-for="(f, i) in faults" :key="i" class="flex items-center gap-2">
            <AlertTriangle class="size-4 text-amber-500" />{{ f }}
          </li>
        </ul>
      </div>
    </CardContent>
  </Card>
</template>
