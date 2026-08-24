export type UserRole = "user" | "admin";
export type AppMode = "simulation";
export type DataSource = "simulation";
export type ConnectionState = "simulated" | "disconnected" | "connecting" | "connected" | "error";
export type DataState = "live" | "stale" | "unavailable";
export type OverallState = "simulation" | "nominal" | "unknown" | "fault";
export type ComponentState = "on" | "off" | "unknown" | "fault";
export type ConditionState = "ok" | "fault" | "unknown";

export interface SessionUser {
  username: string;
  role: UserRole;
  expires_at: string;
}

export interface TelemetryPoint {
  timestamp: string;
  source: DataSource;
  sequence: number;
  ionV: number;
  ionI: number;
  heatV: number;
  heatI: number;
  heLvl: number;
  Thot: number;
  Tcold: number;
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
}

export interface UserRecord {
  username: string;
  role: UserRole;
}

export interface UsersResponse {
  users: UserRecord[];
}
