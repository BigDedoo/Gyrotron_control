<script setup lang="ts">
import { Card, CardHeader, CardTitle, CardContent, Button } from '@/components/ui'
import { AlertTriangle } from 'lucide-vue-next'
import { Badge } from '@/components/ui'

const items = [
  { g: "Environment", k: ["External interlock", "GS Doors", "Waterflow", "Poor vacuum"] },
  { g: "Supplies", k: ["CMPS ON", "GPPS ON", "IPPS ON", "APS ON", "CPS ON"] },
  { g: "Alarms", k: ["ARC detector", "Overcurrent", "Overvoltage", "Temperature"] },
  { g: "Cryo", k: ["Liquid He gauge", "He level normal"] },
]
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
    <Card v-for="grp in items" :key="grp.g" class="rounded-2xl">
      <CardHeader class="pb-2"><CardTitle class="text-sm">{{ grp.g }}</CardTitle></CardHeader>
      <CardContent class="grid grid-cols-1 gap-2">
        <div v-for="k in grp.k" :key="k" class="flex items-center justify-between">
          <span class="text-sm text-muted-foreground">{{ k }}</span>
          <Badge class="rounded-full bg-emerald-500 hover:bg-emerald-600">OK</Badge>
        </div>
      </CardContent>
    </Card>
    <Card class="rounded-2xl">
      <CardHeader class="pb-2"><CardTitle class="text-base flex items-center gap-2"><AlertTriangle class="size-4" /> Actions</CardTitle></CardHeader>
      <CardContent class="space-y-3">
        <Button class="rounded-2xl w-full" variant="secondary">Reset Interlocks</Button>
        <Button class="rounded-2xl w-full" variant="destructive">Emergency Shutdown</Button>
      </CardContent>
    </Card>
  </div>
</template>
