import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { api, ApiError } from '@/api/client'
import type { DataState, SystemStatus } from '@/api/types'

const POLL_DELAY_MS = 2000
const REQUEST_TIMEOUT_MS = 3000
const STALE_AFTER_MS = 6000

export function useSystemStatus(enabled: Ref<boolean>, onUnauthorized: () => void) {
  const systemStatus = ref<SystemStatus | null>(null)
  const statusState = ref<DataState>('unavailable')
  const error = ref<string | null>(null)
  let cleanup = () => {}

  watch(enabled, (isEnabled) => {
    cleanup()
    if (!isEnabled) {
      systemStatus.value = null
      statusState.value = 'unavailable'
      error.value = null
      return
    }

    let active = true
    let pollTimer: ReturnType<typeof setTimeout> | undefined
    let staleTimer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined

    const poll = async () => {
      controller = new AbortController()
      let timedOut = false
      const timeout = setTimeout(() => {
        timedOut = true
        controller?.abort()
      }, REQUEST_TIMEOUT_MS)
      try {
        const next = await api.getSystemStatus(controller.signal)
        const sourceMatches =
          (next.mode === 'simulation' && next.source === 'simulation') ||
          (next.mode === 'opcua_readonly' && next.source === 'opcua')
        if (!sourceMatches || Number.isNaN(Date.parse(next.timestamp))) throw new Error('Malformed status')
        if (!active) return
        systemStatus.value = next
        statusState.value = next.data_state
        error.value = next.monitor_error
        if (staleTimer) clearTimeout(staleTimer)
        staleTimer = setTimeout(() => {
          if (active) {
            statusState.value = 'stale'
            error.value = 'System status is stale.'
          }
        }, STALE_AFTER_MS)
      } catch (caught) {
        if (!active) return
        if (caught instanceof ApiError && caught.status === 401) {
          onUnauthorized()
          return
        }
        if (staleTimer) clearTimeout(staleTimer)
        staleTimer = undefined
        statusState.value = 'unavailable'
        error.value = timedOut ? 'System status request timed out.' : 'System status is unavailable.'
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
  return { systemStatus, statusState, error }
}
