<script setup lang="ts">
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, CustomChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { ref, computed } from 'vue'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui'
import GaugeCard from '@/components/GaugeCard.vue'
import { Gauge, Thermometer } from 'lucide-vue-next'
import type { TelemetryPoint } from '@/composables/useTelemetry'

use([
  CanvasRenderer,
  LineChart,
  CustomChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const props = defineProps<{
  data: TelemetryPoint[]
  latest: TelemetryPoint
}>()

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis'
  },
  legend: {
    data: ['Ion Pump V', 'Ion Pump I', 'Heater V', 'Heater I']
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.data.map((_, i) => i) // Mock time for now, replace with actual time if available
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      name: 'Ion Pump V',
      type: 'line',
      showSymbol: false,
      data: props.data.map(d => d.ionV)
    },
    {
      name: 'Ion Pump I',
      type: 'line',
      showSymbol: false,
      data: props.data.map(d => d.ionI)
    },
    {
      name: 'Heater V',
      type: 'line',
      showSymbol: false,
      data: props.data.map(d => d.heatV)
    },
    {
      name: 'Heater I',
      type: 'line',
      showSymbol: false,
      data: props.data.map(d => d.heatI)
    }
  ]
}))
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
    <Card class="rounded-2xl xl:col-span-2">
      <CardHeader class="pb-2"><CardTitle class="text-base">Live Trends</CardTitle></CardHeader>
      <CardContent>
        <div class="h-64">
           <v-chart class="chart" :option="chartOption" autoresize />
        </div>
      </CardContent>
    </Card>
    <div class="grid grid-cols-1 gap-4">
      <GaugeCard title="Liquid He Level" :value="latest.heLvl" unit=" %" :icon="Gauge" />
      <GaugeCard title="T hot" :value="latest.Thot" unit=" °C" :icon="Thermometer" />
      <GaugeCard title="T cold" :value="latest.Tcold" unit=" °C" :icon="Thermometer" />
    </div>
  </div>
</template>

<style scoped>
.chart {
  height: 100%;
  width: 100%;
}
</style>
