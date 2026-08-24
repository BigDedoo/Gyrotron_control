from datetime import datetime, timezone

from app.core.config import get_settings
from app.models import (
    AlarmSummary,
    ComponentState,
    ComponentStatus,
    ConditionState,
    ConnectionState,
    DataSource,
    DataState,
    InterlockStatus,
    OverallState,
    SystemStatus,
)


INTERLOCK_GROUPS = {
    "Environment": ["External interlock", "GS Doors", "Waterflow", "Poor vacuum"],
    "Supplies": ["CMPS ON", "GPPS ON", "IPPS ON", "APS ON", "CPS ON"],
    "Alarms": ["ARC detector", "Overcurrent", "Overvoltage", "Temperature"],
    "Cryo": ["Liquid He gauge", "He level normal"],
}


def _unknown_component() -> ComponentStatus:
    return ComponentStatus(
        state=ComponentState.UNKNOWN,
        ready=ConditionState.UNKNOWN,
        rectifier=ComponentState.UNKNOWN,
        converter=ComponentState.UNKNOWN,
        protection=ConditionState.UNKNOWN,
    )


def get_system_status() -> SystemStatus:
    settings = get_settings()
    interlocks = [
        InterlockStatus(group=group, name=name, state=ConditionState.UNKNOWN)
        for group, names in INTERLOCK_GROUPS.items()
        for name in names
    ]
    return SystemStatus(
        mode=settings.app_mode,
        source=DataSource.SIMULATION,
        connection_state=ConnectionState.SIMULATED,
        data_state=DataState.LIVE,
        overall_state=OverallState.SIMULATION,
        cps=_unknown_component(),
        aps=_unknown_component(),
        interlocks=interlocks,
        alarms=AlarmSummary(state=ConditionState.UNKNOWN, active=[]),
        timestamp=datetime.now(timezone.utc),
    )
