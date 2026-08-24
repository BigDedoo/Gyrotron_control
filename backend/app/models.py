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


class InterlockStatus(BaseModel):
    group: str
    name: str
    state: ConditionState


class AlarmStatus(BaseModel):
    code: str
    message: str
    severity: str
    active_since: datetime | None = None


class AlarmSummary(BaseModel):
    state: ConditionState
    active: list[AlarmStatus]


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
