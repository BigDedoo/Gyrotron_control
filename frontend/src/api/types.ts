export type UserRole = "user" | "admin";
export type AppMode = "simulation" | "opcua_readonly";
export type DataSource = "simulation" | "opcua";
export type ConnectionState = "simulated" | "disconnected" | "connecting" | "connected" | "error";
export type DataState = "live" | "degraded" | "stale" | "unavailable";
export type OverallState = "simulation" | "nominal" | "unknown" | "fault";
export type ComponentState = "on" | "off" | "unknown" | "fault";
export type ConditionState = "ok" | "fault" | "unknown";
export type SignalQuality = "good" | "uncertain" | "bad" | "unavailable";

export interface SessionUser {
  username: string;
  role: UserRole;
  expires_at: string;
}

export interface SignalValue {
  value: number | null;
  unit: string;
  quality: SignalQuality;
  source_timestamp: string | null;
}

export interface TelemetryPoint {
  timestamp: string;
  source: DataSource;
  sequence: number;
  ionV: SignalValue;
  ionI: SignalValue;
  heatV: SignalValue;
  heatI: SignalValue;
  heLvl: SignalValue;
  Thot: SignalValue;
  Tcold: SignalValue;
}

export interface ComponentStatus {
  state: ComponentState;
  ready: ConditionState;
  rectifier: ComponentState;
  converter: ComponentState;
  protection: ConditionState;
}

export interface InterlockStatus {
  group: string;
  name: string;
  state: ConditionState;
}

export interface AlarmStatus {
  code: string;
  message: string;
  severity: string;
  active_since: string | null;
}

export interface AlarmSummary {
  state: ConditionState;
  active: AlarmStatus[];
}

export interface SystemStatus {
  mode: AppMode;
  source: DataSource;
  connection_state: ConnectionState;
  data_state: DataState;
  overall_state: OverallState;
  cps: ComponentStatus;
  aps: ComponentStatus;
  interlocks: InterlockStatus[];
  alarms: AlarmSummary;
  timestamp: string;
  last_connection_attempt: string | null;
  last_successful_read: string | null;
  monitor_error: string | null;
}

export interface UserRecord {
  username: string;
  role: UserRole;
}

export interface UsersResponse {
  users: UserRecord[];
}
