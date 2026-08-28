from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._@\\-]+$",
    ),
]


class AppMode(str, Enum):
    SIMULATION = "simulation"
    OPCUA_READONLY = "opcua_readonly"


class DataSource(str, Enum):
    SIMULATION = "simulation"
    OPCUA = "opcua"


class SignalQuality(str, Enum):
    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"
    UNAVAILABLE = "unavailable"


class ConnectionState(str, Enum):
    SIMULATED = "simulated"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class DataState(str, Enum):
    LIVE = "live"
    DEGRADED = "degraded"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class OverallState(str, Enum):
    SIMULATION = "simulation"
    NOMINAL = "nominal"
    UNKNOWN = "unknown"
    FAULT = "fault"


class ComponentState(str, Enum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    FAULT = "fault"


class ConditionState(str, Enum):
    OK = "ok"
    FAULT = "fault"
    UNKNOWN = "unknown"


class InterpretedState(str, Enum):
    ON = "on"
    OFF = "off"
    OK = "ok"
    FAULT = "fault"
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class AlarmMonitoringState(str, Enum):
    ACTIVE = "active"
    NO_ACTIVE = "no_active"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"


class AlarmSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EquipmentId(str, Enum):
    SYSTEM = "system"
    CMPS = "cmps"
    CFPS = "cfps"
    IPPS = "ipps"
    ARC_DETECTOR = "arc_detector"
    AHVPS = "ahvps"
    CHVPS = "chvps"
    PULSE_GENERATOR = "pulse_generator"


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class SignalValue(BaseModel):
    value: float | None
    unit: str = Field(min_length=1, max_length=32)
    quality: SignalQuality
    source_timestamp: datetime | None


class TelemetryPoint(BaseModel):
    timestamp: datetime
    source: DataSource
    sequence: int = Field(ge=0)
    ionV: SignalValue
    ionI: SignalValue
    heatV: SignalValue
    heatI: SignalValue
    heLvl: SignalValue
    Thot: SignalValue
    Tcold: SignalValue


class ComponentStatus(BaseModel):
    state: ComponentState
    ready: ConditionState
    rectifier: ComponentState
    converter: ComponentState
    protection: ConditionState
    signals: dict[str, "StateSignalValue"] = Field(default_factory=dict)


class EquipmentStatus(BaseModel):
    state: InterpretedState
    quality: SignalQuality
    data_state: DataState
    feedback: ConditionState | None = None
    interlock: ConditionState | None = None
    protection: ConditionState | None = None
    severity: AlarmSeverity | None = None
    readings: dict[str, SignalValue] = Field(default_factory=dict)


class StateSignalValue(BaseModel):
    logical_name: str
    display_name: str
    group: str
    mapped: bool
    raw_value: bool | int | None
    interpreted_state: InterpretedState
    quality: SignalQuality
    source_timestamp: datetime | None
    observed_at: datetime | None
    source: DataSource
    data_state: DataState
    severity: AlarmSeverity | None = None
    equipment: EquipmentId | None = None


class InterlockStatus(BaseModel):
    logical_name: str
    group: str
    name: str
    state: ConditionState
    signal: StateSignalValue


class AlarmStatus(BaseModel):
    code: str
    message: str
    severity: AlarmSeverity | None
    active_since: datetime | None = None
    signal: StateSignalValue


class AlarmSummary(BaseModel):
    state: ConditionState
    monitoring_state: AlarmMonitoringState
    active: list[AlarmStatus]
    signals: list[StateSignalValue]


class MappingCoverage(BaseModel):
    total: int = Field(ge=0)
    mapped: int = Field(ge=0)
    trustworthy: int = Field(ge=0)
    complete: bool
    missing: list[str]


class MachineStatePoint(BaseModel):
    timestamp: datetime
    source: DataSource
    sequence: int = Field(ge=0)
    signals: dict[str, StateSignalValue]
    coverage: MappingCoverage


class OPCUASnapshot(BaseModel):
    timestamp: datetime
    sequence: int = Field(ge=0)
    telemetry: TelemetryPoint
    machine_state: MachineStatePoint


class SystemStatus(BaseModel):
    mode: AppMode
    source: DataSource
    connection_state: ConnectionState
    data_state: DataState
    overall_state: OverallState
    cps: ComponentStatus
    aps: ComponentStatus
    interlocks: list[InterlockStatus]
    alarms: AlarmSummary
    equipment: dict[str, EquipmentStatus] = Field(default_factory=dict)
    coverage: MappingCoverage
    timestamp: datetime
    last_connection_attempt: datetime | None = None
    last_successful_read: datetime | None = None
    monitor_error: str | None = None


class LoginRequest(BaseModel):
    username: Username
    password: str = Field(min_length=1, max_length=1024)


class SessionUser(BaseModel):
    username: str
    role: UserRole
    expires_at: datetime


class UserRecord(BaseModel):
    username: str
    role: UserRole


class UserCreateRequest(BaseModel):
    username: Username
    role: UserRole = UserRole.USER


class UserUpdateRequest(BaseModel):
    username: Username
    role: UserRole


class UserRemoveRequest(BaseModel):
    username: Username


class UsersResponse(BaseModel):
    users: list[UserRecord]


class MessageResponse(BaseModel):
    message: str
