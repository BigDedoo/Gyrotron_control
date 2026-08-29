from datetime import datetime, timezone

from app.core.config import AppSettings, get_settings
from app.equipment import (
    EQUIPMENT_STATE_SIGNALS,
    build_equipment_snapshot,
    equipment_snapshot_with_data_state,
)
from app.models import (
    AlarmMonitoringState,
    AlarmStatus,
    AlarmSummary,
    ComponentState,
    ComponentStatus,
    ConditionState,
    ConnectionState,
    DataSource,
    DataState,
    EquipmentId,
    InterlockStatus,
    InterpretedState,
    MappingCoverage,
    OverallState,
    SignalQuality,
    SignalValue,
    StateSignalValue,
    SystemStatus,
)
from app.opcua.monitor import MonitorView, OPCUAMonitor
from app.opcua.node_map import (
    LogicalSignal,
    LogicalStateSignal,
    StateSignalKind,
    state_signal_group,
    state_signal_kind,
    state_signal_label,
)
from app.simulation import simulation_snapshot


_EQUIPMENT_BY_STATE_SIGNAL = {
    LogicalStateSignal.CMPS: EquipmentId.CMPS,
    LogicalStateSignal.IPPS: EquipmentId.IPPS,
    LogicalStateSignal.ARC_DETECTOR: EquipmentId.ARC_DETECTOR,
    LogicalStateSignal.OVERVOLTAGE: EquipmentId.AHVPS,
    **EQUIPMENT_STATE_SIGNALS,
}


def _unknown_signal(
    signal: LogicalStateSignal,
    source: DataSource,
    *,
    mapped: bool = False,
    display_name: str | None = None,
    group: str | None = None,
    severity=None,
) -> StateSignalValue:
    return StateSignalValue(
        logical_name=signal.value,
        display_name=display_name or state_signal_label(signal),
        group=group or state_signal_group(signal),
        mapped=mapped,
        raw_value=None,
        interpreted_state=InterpretedState.UNKNOWN,
        quality=SignalQuality.UNAVAILABLE,
        source_timestamp=None,
        observed_at=None,
        source=source,
        data_state=DataState.UNAVAILABLE,
        severity=severity,
        equipment=_EQUIPMENT_BY_STATE_SIGNAL.get(signal),
    )


def _effective_signal(sample: StateSignalValue, data_state: DataState) -> StateSignalValue:
    if data_state in {DataState.STALE, DataState.UNAVAILABLE}:
        return sample.model_copy(
            update={
                "interpreted_state": InterpretedState.UNKNOWN,
                "data_state": data_state,
            }
        )
    if sample.quality == SignalQuality.GOOD:
        return sample
    return sample.model_copy(update={"interpreted_state": InterpretedState.UNKNOWN})


def _trusted(sample: StateSignalValue) -> bool:
    return (
        sample.mapped
        and sample.data_state == DataState.LIVE
        and sample.quality == SignalQuality.GOOD
        and sample.interpreted_state != InterpretedState.UNKNOWN
    )


def _component_state(sample: StateSignalValue) -> ComponentState:
    if not _trusted(sample):
        return ComponentState.UNKNOWN
    return {
        InterpretedState.ON: ComponentState.ON,
        InterpretedState.OFF: ComponentState.OFF,
        InterpretedState.FAULT: ComponentState.FAULT,
    }.get(sample.interpreted_state, ComponentState.UNKNOWN)


def _condition_state(sample: StateSignalValue) -> ConditionState:
    if not _trusted(sample):
        return ConditionState.UNKNOWN
    return {
        InterpretedState.OK: ConditionState.OK,
        InterpretedState.FAULT: ConditionState.FAULT,
    }.get(sample.interpreted_state, ConditionState.UNKNOWN)


def _component(prefix: str, signals: dict[LogicalStateSignal, StateSignalValue]) -> ComponentStatus:
    members = {
        "state": LogicalStateSignal(f"{prefix}.state"),
        "ready": LogicalStateSignal(f"{prefix}.ready"),
        "rectifier": LogicalStateSignal(f"{prefix}.rectifier"),
        "converter": LogicalStateSignal(f"{prefix}.converter"),
        "protection": LogicalStateSignal(f"{prefix}.protection"),
    }
    return ComponentStatus(
        state=_component_state(signals[members["state"]]),
        ready=_condition_state(signals[members["ready"]]),
        rectifier=_component_state(signals[members["rectifier"]]),
        converter=_component_state(signals[members["converter"]]),
        protection=_condition_state(signals[members["protection"]]),
        signals={name: signals[signal] for name, signal in members.items()},
    )


def _coverage(signals: dict[LogicalStateSignal, StateSignalValue]) -> MappingCoverage:
    mapped = sum(sample.mapped for sample in signals.values())
    trustworthy = sum(_trusted(sample) for sample in signals.values())
    return MappingCoverage(
        total=len(LogicalStateSignal),
        mapped=mapped,
        trustworthy=trustworthy,
        complete=mapped == len(LogicalStateSignal) and trustworthy == len(LogicalStateSignal),
        missing=[signal.value for signal, sample in signals.items() if not sample.mapped],
        unavailable=[
            signal.value
            for signal, sample in signals.items()
            if sample.mapped and not _trusted(sample)
        ],
    )


def _machine_state(
    source: DataSource,
    monitor: OPCUAMonitor | None,
    data_state: DataState,
    view: MonitorView | None = None,
) -> dict[LogicalStateSignal, StateSignalValue]:
    configured = {}
    node_map = getattr(monitor, "node_map", None)
    if node_map is not None:
        configured = node_map.states_by_signal()

    observed = {}
    view = view if view is not None else (monitor.view() if monitor is not None else None)
    if view is not None and view.snapshot is not None:
        machine_state = getattr(view.snapshot, "machine_state", None)
        if machine_state is not None:
            observed = machine_state.signals

    result: dict[LogicalStateSignal, StateSignalValue] = {}
    for signal in LogicalStateSignal:
        mapping = configured.get(signal)
        sample = observed.get(signal.value)
        if sample is None:
            sample = _unknown_signal(
                signal,
                source,
                mapped=mapping is not None,
                display_name=mapping.label if mapping is not None else None,
                group=mapping.display_group if mapping is not None else None,
                severity=mapping.alarm_severity if mapping is not None else None,
            )
        sample = _effective_signal(sample, data_state)
        equipment = _EQUIPMENT_BY_STATE_SIGNAL.get(signal)
        if sample.equipment is None and equipment is not None:
            sample = sample.model_copy(update={"equipment": equipment})
        result[signal] = sample
    return result


def _configured_equipment_readings(
    monitor: OPCUAMonitor | None,
) -> dict[LogicalSignal, SignalValue]:
    node_map = getattr(monitor, "node_map", None)
    if node_map is None:
        return {}
    return {
        signal: SignalValue(
            value=None,
            unit=mapping.unit,
            quality=SignalQuality.UNAVAILABLE,
            source_timestamp=None,
            observed_at=None,
            mapped=True,
        )
        for signal, mapping in node_map.by_signal().items()
    }


def get_system_status(
    settings: AppSettings | None = None,
    monitor: OPCUAMonitor | None = None,
) -> SystemStatus:
    settings = settings or get_settings()
    if settings.app_mode.value == "simulation":
        snapshot = simulation_snapshot(
            problem_cycle_seconds=settings.simulation_problem_cycle_seconds
        )
        source = DataSource.SIMULATION
        connection_state = ConnectionState.SIMULATED
        data_state = snapshot.data_state
        last_connection_attempt = None
        last_successful_read = None
        monitor_error = None
        equipment = snapshot.equipment
        signals = snapshot.state_signals
        status_timestamp = snapshot.timestamp
    else:
        view = monitor.view() if monitor is not None else None
        source = DataSource.OPCUA
        connection_state = view.connection_state if view is not None else ConnectionState.ERROR
        data_state = view.data_state if view is not None else DataState.UNAVAILABLE
        last_connection_attempt = view.last_connection_attempt if view is not None else None
        last_successful_read = view.last_successful_read if view is not None else None
        monitor_error = view.error if view is not None else "OPC UA monitor is unavailable"
        signals = _machine_state(source, monitor, data_state, view)
        monitor_snapshot = view.snapshot if view is not None else None
        status_timestamp = (
            monitor_snapshot.timestamp
            if monitor_snapshot is not None
            else datetime.now(timezone.utc)
        )
        cached_equipment = (
            getattr(monitor_snapshot, "equipment", None)
            if monitor_snapshot is not None
            else None
        )
        equipment = (
            equipment_snapshot_with_data_state(cached_equipment, data_state)
            if cached_equipment is not None
            else build_equipment_snapshot(
                source=DataSource.OPCUA,
                timestamp=status_timestamp,
                sequence=0,
                data_state=data_state,
                readings=_configured_equipment_readings(monitor),
                state_signals=signals,
            )
        )

    coverage = _coverage(signals)
    cps = _component("cps", signals)
    aps = _component("aps", signals)

    interlocks = [
        InterlockStatus(
            logical_name=signal.value,
            group=sample.group,
            name=sample.display_name,
            state=_condition_state(sample),
            signal=sample,
        )
        for signal, sample in signals.items()
        if state_signal_kind(signal) == StateSignalKind.INTERLOCK
    ]

    alarm_signals = [
        sample
        for signal, sample in signals.items()
        if state_signal_kind(signal) == StateSignalKind.ALARM
    ]
    active = [
        AlarmStatus(
            code=sample.logical_name,
            message=sample.display_name,
            severity=sample.severity,
            signal=sample,
        )
        for sample in alarm_signals
        if _trusted(sample) and sample.interpreted_state == InterpretedState.ACTIVE
    ]
    alarms_complete = all(_trusted(sample) for sample in alarm_signals)
    if active:
        alarm_state = ConditionState.FAULT
        alarm_monitoring_state = AlarmMonitoringState.ACTIVE
    elif alarms_complete:
        alarm_state = ConditionState.OK
        alarm_monitoring_state = AlarmMonitoringState.NO_ACTIVE
    elif data_state == DataState.UNAVAILABLE:
        alarm_state = ConditionState.UNKNOWN
        alarm_monitoring_state = AlarmMonitoringState.UNAVAILABLE
    else:
        alarm_state = ConditionState.UNKNOWN
        alarm_monitoring_state = AlarmMonitoringState.INCOMPLETE
    alarms = AlarmSummary(
        state=alarm_state,
        monitoring_state=alarm_monitoring_state,
        active=active,
        signals=alarm_signals,
    )

    confirmed_fault = any(
        _trusted(sample)
        and sample.interpreted_state in {InterpretedState.FAULT, InterpretedState.ACTIVE}
        for sample in signals.values()
    )
    if settings.app_mode.value == "simulation":
        overall_state = OverallState.SIMULATION
    elif confirmed_fault:
        overall_state = OverallState.FAULT
    elif coverage.complete:
        overall_state = OverallState.NOMINAL
    else:
        overall_state = OverallState.UNKNOWN

    return SystemStatus(
        mode=settings.app_mode,
        source=source,
        connection_state=connection_state,
        data_state=data_state,
        overall_state=overall_state,
        cps=cps,
        aps=aps,
        interlocks=interlocks,
        alarms=alarms,
        equipment=equipment,
        coverage=coverage,
        timestamp=status_timestamp,
        last_connection_attempt=last_connection_attempt,
        last_successful_read=last_successful_read,
        monitor_error=monitor_error,
    )
