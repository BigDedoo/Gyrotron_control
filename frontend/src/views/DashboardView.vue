<script setup lang="ts">
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { computed } from 'vue'
import { Card, CardHeader, CardTitle, CardContent, Badge } from '@/components/ui'
import GaugeCard from '@/components/GaugeCard.vue'
import QuickStatus from '@/components/QuickStatus.vue'
import { Activity, Gauge, Zap, Flame, Thermometer, Timer } from 'lucide-vue-next'
import type { TelemetryPoint } from '@/composables/useTelemetry'

use([CanvasRenderer, LineChart, TooltipComponent, GridComponent])

const props = defineProps<{
  cpsOn: boolean
  apsOn: boolean
  faults: string[]
  data: TelemetryPoint[]
  latest: TelemetryPoint
}>()

const ok = computed(() => props.faults.length === 0)

function getChartOption(dataKey: keyof TelemetryPoint, color: string) {
  return computed(() => ({
    grid: { left: 0, right: 0, top: 10, bottom: 0 },
    xAxis: { type: 'category', show: false, data: props.data.map((_, i) => i) },
    yAxis: { type: 'value', show: false, min: 0 },
    tooltip: { trigger: 'axis' },
    series: [
      {
        data: props.data.map((d) => d[dataKey]),
        type: 'line',
        smooth: true,
        showSymbol: false,
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: color },
              { offset: 1, color: 'rgba(255, 255, 255, 0)' }
            ]
          }
        },
        lineStyle: { width: 2, color: color }
      }
    ]
  }))
}

const heaterOption = getChartOption('heatV', '#8884d8')
const ionOption = getChartOption('ionI', '#82ca9d')
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
    <Card class="rounded-2xl xl:col-span-2">
      <CardHeader class="pb-2 flex flex-row items-center justify-between">
        <CardTitle class="flex items-center gap-2 text-base"
          ><Activity class="size-4" /> System Overview</CardTitle
        >
        <Badge :variant="ok ? 'default' : 'destructive'" class="text-xs px-3 py-1 rounded-full">{{
          ok ? 'All systems nominal' : `${faults.length} alarm(s)`
        }}</Badge>
      </CardHeader>
      <CardContent>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <GaugeCard title="Ion Pump V" :value="latest.ionV" unit=" V" :icon="Gauge" />
          <GaugeCard title="Ion Pump I" :value="latest.ionI" unit=" A" :icon="Zap" />
          <GaugeCard title="Heater V" :value="latest.heatV" unit=" V" :icon="Flame" />
          <GaugeCard title="Heater I" :value="latest.heatI" unit=" A" :icon="Zap" />
          <GaugeCard title="Liquid He Level" :value="latest.heLvl" unit=" %" :icon="Gauge" />
          <GaugeCard title="T hot" :value="latest.Thot" unit=" °C" :icon="Thermometer" />
          <GaugeCard title="T cold" :value="latest.Tcold" unit=" °C" :icon="Thermometer" />
          <GaugeCard title="Pulse Duration" :value="2.5" unit=" ms" :icon="Timer" />
        </div>
        <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card class="rounded-2xl">
            <CardHeader class="pb-2"
              ><CardTitle class="text-sm">Heater Voltage (live)</CardTitle></CardHeader
            >
            <CardContent>
              <div class="h-40">
                <v-chart class="chart" :option="heaterOption" autoresize />
              </div>
            </CardContent>
          </Card>
          <Card class="rounded-2xl">
            <CardHeader class="pb-2"
              ><CardTitle class="text-sm">Ion Pump Current (live)</CardTitle></CardHeader
            >
            <CardContent>
              <div class="h-40">
                <v-chart class="chart" :option="ionOption" autoresize />
              </div>
            </CardContent>
          </Card>
        </div>
      </CardContent>
    </Card>

    <QuickStatus :cpsOn="cpsOn" :apsOn="apsOn" :faults="faults" />
  </div>
</template>

<style scoped>
.chart {
  height: 100%;
  width: 100%;
}
</style>
