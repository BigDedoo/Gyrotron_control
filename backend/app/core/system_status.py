from datetime import datetime, timezone

from app.core.config import AppSettings, get_settings
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
from app.opcua.monitor import OPCUAMonitor


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


def get_system_status(
    settings: AppSettings | None = None,
    monitor: OPCUAMonitor | None = None,
) -> SystemStatus:
    settings = settings or get_settings()
    interlocks = [
        InterlockStatus(group=group, name=name, state=ConditionState.UNKNOWN)
        for group, names in INTERLOCK_GROUPS.items()
        for name in names
    ]
    if settings.app_mode.value == "simulation":
        source = DataSource.SIMULATION
        connection_state = ConnectionState.SIMULATED
        data_state = DataState.LIVE
        overall_state = OverallState.SIMULATION
        last_connection_attempt = None
        last_successful_read = None
        monitor_error = None
    else:
        view = monitor.view() if monitor is not None else None
        source = DataSource.OPCUA
        connection_state = (
            view.connection_state if view is not None else ConnectionState.ERROR
        )
        data_state = view.data_state if view is not None else DataState.UNAVAILABLE
        overall_state = OverallState.UNKNOWN
        last_connection_attempt = view.last_connection_attempt if view is not None else None
        last_successful_read = view.last_successful_read if view is not None else None
        monitor_error = view.error if view is not None else "OPC UA monitor is unavailable"

    return SystemStatus(
        mode=settings.app_mode,
        source=source,
        connection_state=connection_state,
        data_state=data_state,
        overall_state=overall_state,
        cps=_unknown_component(),
        aps=_unknown_component(),
        interlocks=interlocks,
        alarms=AlarmSummary(state=ConditionState.UNKNOWN, active=[]),
        timestamp=datetime.now(timezone.utc),
        last_connection_attempt=last_connection_attempt,
        last_successful_read=last_successful_read,
        monitor_error=monitor_error,
    )
