import { ref, computed } from 'vue'
import { useIntervalFn } from '@vueuse/core'

export interface TelemetryPoint {
  time: number
  ionV: number
  ionI: number
  heatV: number
  heatI: number
  heLvl: number
  Thot: number
  Tcold: number
}

export function useTelemetry() {
  const data = ref<TelemetryPoint[]>([])

  const { pause, resume, isActive } = useIntervalFn(async () => {
    try {
      const res = await fetch('/api/telemetry')
      if (!res.ok) throw new Error('Failed to fetch')
      const point = await res.json()

      data.value.push(point)
      if (data.value.length > 40) {
        data.value.shift()
      }
    } catch (err) {
      console.error('Telemetry fetch error:', err)
    }
  }, 1000)

  const latest = computed(() => {
    return (
      data.value[data.value.length - 1] || {
        time: 0,
        ionV: 0,
        ionI: 0,
        heatV: 0,
        heatI: 0,
        heLvl: 0,
        Thot: 0,
        Tcold: 0
      }
    )
  })

  return { data, latest, pause, resume, isActive }
}
