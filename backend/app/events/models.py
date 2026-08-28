from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models import AlarmSeverity, EquipmentId


class EventCategory(str, Enum):
    APPLICATION = "application"
    MONITORING = "monitoring"
    MACHINE_STATE = "machine_state"
    INTERLOCK = "interlock"
    ALARM = "alarm"
    SECURITY = "security"
    OPERATOR = "operator"
    COMMAND = "command"


class EventState(str, Enum):
    ACTIVE = "active"
    RECOVERED = "recovered"
    CHANGED = "changed"


class EventCreate(BaseModel):
    recorded_at: datetime | None = None
    source_timestamp: datetime | None = None
    category: EventCategory
    event_type: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=64)
    severity: AlarmSeverity | None = None
    equipment: EquipmentId | None = None
    state: EventState | None = None
    actor: str | None = Field(default=None, max_length=128)
    target: str | None = Field(default=None, max_length=256)
    message: str = Field(min_length=1, max_length=1024)
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=128)


class EventRecord(BaseModel):
    id: int = Field(gt=0)
    recorded_at: datetime
    source_timestamp: datetime | None
    category: EventCategory
    event_type: str
    source: str
    severity: AlarmSeverity | None
    equipment: EquipmentId | None = None
    state: EventState | None = None
    actor: str | None
    target: str | None
    message: str
    details: dict[str, Any]
    correlation_id: str | None


class EventListResponse(BaseModel):
    events: list[EventRecord]
    next_before_id: int | None
    store_available: bool
