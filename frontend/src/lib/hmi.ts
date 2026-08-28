import type { AlarmSeverity, SignalValue } from '@/api/types'

export function hmiTone(state: string | null | undefined) {
  const normalized = (state ?? 'unknown').toLowerCase()
  if (['fault', 'active', 'critical', 'error', 'disconnected', 'bad'].includes(normalized)) return 'danger'
  if (['degraded', 'stale', 'uncertain', 'warning', 'connecting', 'simulation'].includes(normalized)) return 'warning'
  if (['nominal', 'ok', 'on', 'ready', 'connected', 'live', 'good', 'no_active'].includes(normalized)) return 'healthy'
  if (['opcua_readonly', 'simulated', 'info'].includes(normalized)) return 'info'
  return 'neutral'
}

export function stateLabel(state: string | null | undefined) {
  if (state === 'unmapped') return 'NOT MAPPED'
  return (state ?? 'unknown').replace(/_/g, ' ').toUpperCase()
}

export function formatTimestamp(value: string | null | undefined) {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

export function formatSignal(signal: SignalValue | null | undefined, digits = 1) {
  if (!signal || signal.value === null || signal.quality === 'bad' || signal.quality === 'unavailable') return '—'
  return `${signal.value.toFixed(digits)} ${signal.unit}`.trim()
}

export function highestSeverity(values: Array<AlarmSeverity | null>) {
  if (values.includes('critical')) return 'critical'
  if (values.includes('warning')) return 'warning'
  if (values.includes('info')) return 'info'
  return null
}
