<script setup lang="ts">
import { computed, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { TelemetryPoint } from '@/api/types'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

type SignalKey = 'ionV' | 'ionI' | 'heatV' | 'heatI' | 'heLvl' | 'Thot' | 'Tcold'
const props = defineProps<{ data: TelemetryPoint[] }>()
const definitions: Array<{ key: SignalKey; label: string; color: string }> = [
  { key: 'heatV', label: 'Heater V', color: '#7c3aed' },
  { key: 'heatI', label: 'Heater I', color: '#db2777' },
  { key: 'ionV', label: 'Ion V', color: '#2563eb' },
  { key: 'ionI', label: 'Ion I', color: '#059669' },
  { key: 'heLvl', label: 'He level', color: '#0891b2' },
  { key: 'Thot', label: 'T hot', color: '#ea580c' },
  { key: 'Tcold', label: 'T cold', color: '#64748b' }
]
const selected = ref<SignalKey[]>(['heatV', 'heatI'])

function toggle(key: SignalKey) {
  selected.value = selected.value.includes(key)
    ? selected.value.filter((value) => value !== key)
    : [...selected.value, key]
}

const option = computed(() => ({
  animation: false,
  color: definitions.map((item) => item.color),
  tooltip: { trigger: 'axis' },
  legend: { top: 0, textStyle: { fontSize: 10 } },
  grid: { left: 48, right: 16, top: 34, bottom: 28 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    axisLabel: { fontSize: 9 },
    data: props.data.map((point) => new Date(point.timestamp).toLocaleTimeString())
  },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 9 }, splitLine: { lineStyle: { color: '#e2e8f0' } } },
  series: definitions
    .filter((item) => selected.value.includes(item.key))
    .map((item) => ({
      name: item.label,
      type: 'line',
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.5 },
      data: props.data.map((point) => point[item.key].value)
    }))
}))
</script>

<template>
  <section class="rounded-lg border bg-white shadow-sm">
    <div class="flex items-center justify-between gap-3 border-b px-3 py-2">
      <h2 class="text-xs font-bold uppercase tracking-[0.14em] text-slate-700">Live trends</h2>
      <div class="flex flex-wrap justify-end gap-1">
        <button
          v-for="item in definitions"
          :key="item.key"
          :class="[
            'rounded border px-2 py-1 text-[10px] font-medium transition-colors',
            selected.includes(item.key) ? 'border-slate-700 bg-slate-800 text-white' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
          ]"
          @click="toggle(item.key)"
        >
          {{ item.label }}
        </button>
      </div>
    </div>
    <div class="h-52 px-1 py-1">
      <v-chart class="size-full" :option="option" autoresize />
    </div>
  </section>
</template>
