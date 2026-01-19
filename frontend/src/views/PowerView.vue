<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardHeader, CardTitle, CardContent, Button, Slider, Switch, Badge } from '@/components/ui'
import Labeled from '@/components/Labeled.vue'
import { Settings, Power } from 'lucide-vue-next'

const pulse = ref([2.5])
const vcath = ref([6.0])
const vanode = ref([5.0])
const cpsCmd = ref({ rect: false, conv: false })
const apsCmd = ref({ rect: false, conv: false })
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
    <Card class="rounded-2xl xl:col-span-2">
      <CardHeader class="pb-2"><CardTitle class="text-base flex items-center gap-2"><Settings class="size-4" /> Setpoints</CardTitle></CardHeader>
      <CardContent class="space-y-6">
        <Labeled :label="`Pulse duration: ${pulse[0].toFixed(2)} ms`">
          <div id="setpoint-pulse">
            <Slider v-model="pulse" :min="0" :max="10" :step="0.1" />
          </div>
        </Labeled>
        <Labeled :label="`Cathode voltage: ${vcath[0].toFixed(2)} V`">
          <div id="setpoint-cathode">
            <Slider v-model="vcath" :min="0" :max="10" :step="0.1" />
          </div>
        </Labeled>
        <Labeled :label="`Anode voltage: ${vanode[0].toFixed(2)} V`">
          <div id="setpoint-anode">
            <Slider v-model="vanode" :min="0" :max="10" :step="0.1" />
          </div>
        </Labeled>
        <div class="flex gap-3 pt-2">
          <Button id="apply-setpoints" class="rounded-2xl">Apply Setpoints</Button>
          <Button variant="outline" class="rounded-2xl">Revert</Button>
        </div>
      </CardContent>
    </Card>

    <div class="grid grid-cols-1 gap-4">
      <Card class="rounded-2xl">
        <CardHeader class="pb-2"><CardTitle class="text-sm flex items-center gap-2"><Power class="size-4" /> CPS Commands</CardTitle></CardHeader>
        <CardContent class="space-y-3">
          <Labeled label="Power Rectifier">
            <div id="cps-rectifier" class="flex items-center gap-3">
              <Switch v-model:checked="cpsCmd.rect" />
              <Badge :variant="cpsCmd.rect ? 'default' : 'secondary'">{{ cpsCmd.rect ? "ON" : "OFF" }}</Badge>
            </div>
          </Labeled>
          <Labeled label="Charging Converter">
            <div id="cps-converter" class="flex items-center gap-3">
              <Switch v-model:checked="cpsCmd.conv" />
              <Badge :variant="cpsCmd.conv ? 'default' : 'secondary'">{{ cpsCmd.conv ? "ON" : "OFF" }}</Badge>
            </div>
          </Labeled>
          <div class="flex gap-3 pt-2">
            <Button class="rounded-2xl" variant="secondary">Protection Reset</Button>
            <Button class="rounded-2xl" variant="outline">Apply</Button>
          </div>
        </CardContent>
      </Card>

      <Card class="rounded-2xl">
        <CardHeader class="pb-2"><CardTitle class="text-sm flex items-center gap-2"><Power class="size-4" /> APS Commands</CardTitle></CardHeader>
        <CardContent class="space-y-3">
          <Labeled label="Power Rectifier">
            <div id="aps-rectifier" class="flex items-center gap-3">
              <Switch v-model:checked="apsCmd.rect" />
              <Badge :variant="apsCmd.rect ? 'default' : 'secondary'">{{ apsCmd.rect ? "ON" : "OFF" }}</Badge>
            </div>
          </Labeled>
          <Labeled label="Charging Converter">
            <div id="aps-converter" class="flex items-center gap-3">
              <Switch v-model:checked="apsCmd.conv" />
              <Badge :variant="apsCmd.conv ? 'default' : 'secondary'">{{ apsCmd.conv ? "ON" : "OFF" }}</Badge>
            </div>
          </Labeled>
          <div class="flex gap-3 pt-2">
            <Button class="rounded-2xl" variant="secondary">Protection Reset</Button>
            <Button class="rounded-2xl" variant="outline">Apply</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
