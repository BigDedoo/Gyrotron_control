export type UserRole = 'user' | 'admin'
export type AppMode = 'simulation' | 'opcua_readonly'
export type DataSource = 'simulation' | 'opcua'
export type ConnectionState = 'simulated' | 'disconnected' | 'connecting' | 'connected' | 'error'
export type DataState = 'live' | 'degraded' | 'stale' | 'unavailable'
export type OverallState = 'simulation' | 'nominal' | 'unknown' | 'fault'
export type ComponentState = 'on' | 'off' | 'unknown' | 'fault'
export type ConditionState = 'ok' | 'fault' | 'unknown'
export type SignalQuality = 'good' | 'uncertain' | 'bad' | 'unavailable'
export type InterpretedState = 'on' | 'off' | 'ok' | 'fault' | 'active' | 'inactive' | 'unknown'
export type AlarmMonitoringState = 'active' | 'no_active' | 'incomplete' | 'unavailable'
export type AlarmSeverity = 'info' | 'warning' | 'critical'
export type EventCategory = 'application' | 'monitoring' | 'machine_state' | 'interlock' | 'alarm' | 'security' | 'operator' | 'command'
export type EventState = 'active' | 'recovered' | 'changed'
export type EquipmentId = 'system' | 'cmps' | 'cfps' | 'ipps' | 'arc_detector' | 'ahvps' | 'chvps' | 'pulse_generator'
export type LogicalCommand = 'setpoint.apply' | 'cps.rectifier.set' | 'cps.converter.set' | 'aps.rectifier.set' | 'aps.converter.set' | 'protection.reset' | 'interlock.reset' | 'emergency.shutdown'

export interface SessionUser {
  username: string
  role: UserRole
  expires_at: string
}

export interface SignalValue {
  value: number | null
  unit: string
  quality: SignalQuality
  source_timestamp: string | null
  observed_at: string | null
  mapped: boolean
}

export interface TelemetryPoint {
  timestamp: string
  source: DataSource
  sequence: number
  ionV: SignalValue
  ionI: SignalValue
  heatV: SignalValue
  heatI: SignalValue
  heLvl: SignalValue
  Thot: SignalValue
  Tcold: SignalValue
}

export interface StateSignalValue {
  logical_name: string
  display_name: string
  group: string
  mapped: boolean
  raw_value: boolean | number | null
  interpreted_state: InterpretedState
  quality: SignalQuality
  source_timestamp: string | null
  observed_at: string | null
  source: DataSource
  data_state: DataState
  severity: AlarmSeverity | null
  equipment: EquipmentId | null
}

export interface ComponentStatus {
  state: ComponentState
  ready: ConditionState
  rectifier: ComponentState
  converter: ComponentState
  protection: ConditionState
  signals: Record<string, StateSignalValue>
}

export interface EquipmentStatusBase {
  state: StateSignalValue
  quality: SignalQuality
  data_state: DataState
}

export interface CMPSEquipmentStatus extends EquipmentStatusBase {
  current: SignalValue
  interlock: StateSignalValue
}

export interface CFPSEquipmentStatus extends EquipmentStatusBase {
  power: SignalValue
  feedback: StateSignalValue
  interlock: StateSignalValue
}

export interface IPPSEquipmentStatus extends EquipmentStatusBase {
  voltage: SignalValue
  current: SignalValue
  interlock: StateSignalValue
}

export interface ArcDetectorEquipmentStatus extends EquipmentStatusBase {
  severity: AlarmSeverity | null
}

export interface HVPSSupplyEquipmentStatus extends EquipmentStatusBase {
  voltage: SignalValue
  protection: StateSignalValue
  interlock: StateSignalValue
}

export interface HVPSEquipmentStatus {
  ahvps: HVPSSupplyEquipmentStatus
  chvps: HVPSSupplyEquipmentStatus
}

export interface PulseGeneratorEquipmentStatus extends EquipmentStatusBase {
  pulse_length: SignalValue
  pulse_period: SignalValue
  feedback: StateSignalValue
}

export interface EquipmentSnapshot {
  timestamp: string
  source: DataSource
  sequence: number
  data_state: DataState
  cmps: CMPSEquipmentStatus
  cfps: CFPSEquipmentStatus
  ipps: IPPSEquipmentStatus
  arc_detector: ArcDetectorEquipmentStatus
  hvps: HVPSEquipmentStatus
  pulse_generator: PulseGeneratorEquipmentStatus
  coverage: MappingCoverage
}

export interface InterlockStatus {
  logical_name: string
  group: string
  name: string
  state: ConditionState
  signal: StateSignalValue
}

export interface AlarmStatus {
  code: string
  message: string
  severity: AlarmSeverity | null
  active_since: string | null
  signal: StateSignalValue
}

export interface AlarmSummary {
  state: ConditionState
  monitoring_state: AlarmMonitoringState
  active: AlarmStatus[]
  signals: StateSignalValue[]
}

export interface MappingCoverage {
  total: number
  mapped: number
  trustworthy: number
  complete: boolean
  missing: string[]
  unavailable: string[]
}

export interface SystemStatus {
  mode: AppMode
  source: DataSource
  connection_state: ConnectionState
  data_state: DataState
  overall_state: OverallState
  cps: ComponentStatus
  aps: ComponentStatus
  interlocks: InterlockStatus[]
  alarms: AlarmSummary
  equipment: EquipmentSnapshot
  coverage: MappingCoverage
  timestamp: string
  last_connection_attempt: string | null
  last_successful_read: string | null
  monitor_error: string | null
}

export interface UserRecord {
  username: string
  role: UserRole
}

export interface UsersResponse {
  users: UserRecord[]
}

export interface EventRecord {
  id: number
  recorded_at: string
  source_timestamp: string | null
  category: EventCategory
  event_type: string
  source: string
  severity: AlarmSeverity | null
  equipment: EquipmentId | null
  state: EventState | null
  actor: string | null
  target: string | null
  message: string
  details: Record<string, unknown>
  correlation_id: string | null
}

export interface EventListResponse {
  events: EventRecord[]
  next_before_id: number | null
  store_available: boolean
}

export interface CommandCapability {
  command: LogicalCommand
  target: string
  available: false
  blockers: string[]
  reasons: string[]
}

export interface CommandCapabilitiesResponse {
  capabilities: CommandCapability[]
  execution_available: false
}

export type OPCUADiagnosticsEnvironment = 'simulation' | 'local_opcua_test' | 'production_opcua'
export type OPCUAMappingStatus = 'ready' | 'degraded' | 'stale' | 'bad_quality' | 'type_mismatch' | 'unavailable' | 'not_observed'

export interface OPCUASignalDiagnostic {
  equipment: string
  logical_field: string
  node_id: string
  expected_datatype: string
  observed_datatype: string | null
  raw_value: boolean | number | string | null
  converted_value: boolean | number | null
  quality: SignalQuality
  source_timestamp: string | null
  backend_observed_at: string | null
  age_seconds: number | null
  connection_state: ConnectionState
  last_successful_read: string | null
  last_error: string | null
  scale: number | null
  offset: number | null
  mapping_status: OPCUAMappingStatus
}

export interface OPCUADiagnosticsResponse {
  environment: OPCUADiagnosticsEnvironment
  telemetry_capability: 'simulated' | 'available_config_dependent'
  plc_command_capability: 'unsupported_disabled'
  read_only: true
  connection_state: ConnectionState
  last_successful_read: string | null
  last_error: string | null
  signals: OPCUASignalDiagnostic[]
}
