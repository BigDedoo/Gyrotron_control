import { computed, onScopeDispose, ref, watch, type Ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { DataState, SignalQuality, SignalValue, TelemetryPoint } from '@/api/types'

const SIGNAL_KEYS = ['ionV', 'ionI', 'heatV', 'heatI', 'heLvl', 'Thot', 'Tcold'] as const
const QUALITY_VALUES: SignalQuality[] = ['good', 'uncertain', 'bad', 'unavailable']
const POLL_DELAY_MS = 1000
const REQUEST_TIMEOUT_MS = 3000
const STALE_AFTER_MS = 5000
const BUFFER_SIZE = 40

function validateSignal(sample: SignalValue) {
  const usable = sample.quality === 'good' || sample.quality === 'uncertain'
  if (
    !QUALITY_VALUES.includes(sample.quality) ||
    !sample.unit ||
    (sample.source_timestamp !== null && Number.isNaN(Date.parse(sample.source_timestamp))) ||
    (usable && (sample.value === null || !Number.isFinite(sample.value))) ||
    (!usable && sample.value !== null)
  ) throw new Error('Telemetry signal is malformed')
}

function validateTelemetry(point: TelemetryPoint): DataState {
  if (!['simulation', 'opcua'].includes(point.source) || Number.isNaN(Date.parse(point.timestamp))) {
    throw new Error('Telemetry response is malformed')
  }
  const samples = SIGNAL_KEYS.map((key) => point[key])
  samples.forEach(validateSignal)
  return samples.every((sample) => sample.quality === 'good') ? 'live' : 'degraded'
}

export function useTelemetry(enabled: Ref<boolean>, onUnauthorized: () => void) {
  const data = ref<TelemetryPoint[]>([])
  const dataState = ref<DataState>('unavailable')
  const lastSuccessfulAt = ref<string | null>(null)
  const error = ref<string | null>(null)
  let cleanup = () => {}

  watch(enabled, (isEnabled) => {
    cleanup()
    if (!isEnabled) {
      data.value = []
      dataState.value = 'unavailable'
      lastSuccessfulAt.value = null
      error.value = null
      return
    }

    let active = true
    let pollTimer: ReturnType<typeof setTimeout> | undefined
    let staleTimer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined

    const scheduleStale = () => {
      if (staleTimer) clearTimeout(staleTimer)
      staleTimer = setTimeout(() => {
        if (active) {
          dataState.value = 'stale'
          error.value = 'Telemetry is stale; displayed values are not current.'
        }
      }, STALE_AFTER_MS)
    }

    const poll = async () => {
      controller = new AbortController()
      let timedOut = false
      const timeout = setTimeout(() => {
        timedOut = true
        controller?.abort()
      }, REQUEST_TIMEOUT_MS)
      try {
        const point = await api.getTelemetry(controller.signal)
        const nextState = validateTelemetry(point)
        if (!active) return
        data.value = [...data.value, point].slice(-BUFFER_SIZE)
        dataState.value = nextState
        lastSuccessfulAt.value = point.timestamp
        error.value = nextState === 'degraded' ? 'One or more telemetry signals are degraded.' : null
        scheduleStale()
      } catch (caught) {
        if (!active) return
        if (caught instanceof ApiError && caught.status === 401) {
          onUnauthorized()
          return
        }
        if (caught instanceof ApiError && caught.status === 503) {
          dataState.value = caught.message.toLowerCase().includes('unavailable') ? 'unavailable' : 'stale'
          error.value = caught.message
        } else {
          dataState.value = data.value.length ? 'stale' : 'unavailable'
          error.value = timedOut ? 'Telemetry request timed out.' : 'Telemetry is unavailable.'
        }
      } finally {
        clearTimeout(timeout)
        if (active) pollTimer = setTimeout(poll, POLL_DELAY_MS)
      }
    }

    void poll()
    cleanup = () => {
      active = false
      controller?.abort()
      if (pollTimer) clearTimeout(pollTimer)
      if (staleTimer) clearTimeout(staleTimer)
    }
  }, { immediate: true })

  onScopeDispose(() => cleanup())
  return {
    data,
    latest: computed(() => data.value[data.value.length - 1] ?? null),
    dataState,
    lastSuccessfulAt,
    error
  }
}
