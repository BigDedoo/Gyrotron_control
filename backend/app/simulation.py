import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.events.models import EventCategory, EventCreate, EventState
from app.events.store import EventStore, EventStoreUnavailable
from app.models import (
    AlarmSeverity,
    ConditionState,
    DataSource,
    DataState,
    EquipmentId,
    EquipmentStatus,
    InterpretedState,
    SignalQuality,
    SignalValue,
    StateSignalValue,
    TelemetryPoint,
)
from app.opcua.node_map import (
    LogicalStateSignal,
    StateSignalKind,
    state_signal_group,
    state_signal_kind,
    state_signal_label,
)


SIMULATION_SEED_VERSION = "simulation.seed.v1"
DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS = 900.0
_REFERENCE_PROBLEM_CYCLE_SECONDS = 180.0
_started_at = time.monotonic()


@dataclass(frozen=True)
class SimulationSnapshot:
    timestamp: datetime
    elapsed: float
    data_state: DataState
    telemetry: TelemetryPoint
    equipment: dict[str, EquipmentStatus]
    state_signals: dict[LogicalStateSignal, StateSignalValue]


def elapsed_seconds() -> float:
    return max(0.0, time.monotonic() - _started_at)


def _wave(base: float, amplitude: float, period: float, elapsed: float, phase: float = 0.0) -> float:
    slow = math.sin((elapsed / period) * math.tau + phase)
    texture = math.sin((elapsed / (period / 4.7)) * math.tau + phase / 2) * 0.12
    return base + amplitude * (slow + texture)


def _quality(data_state: DataState) -> SignalQuality:
    if data_state == DataState.LIVE:
        return SignalQuality.GOOD
    if data_state in {DataState.DEGRADED, DataState.STALE}:
        return SignalQuality.UNCERTAIN
    return SignalQuality.UNAVAILABLE


def _signal(value: float, unit: str, timestamp: datetime, data_state: DataState) -> SignalValue:
    quality = _quality(data_state)
    return SignalValue(
        value=None if data_state == DataState.UNAVAILABLE else round(value, 3),
        unit=unit,
        quality=quality,
        source_timestamp=None if data_state == DataState.UNAVAILABLE else timestamp,
    )


def _scenario(elapsed: float, problem_cycle_seconds: float) -> dict[str, bool]:
    phase = (elapsed % problem_cycle_seconds) / problem_cycle_seconds
    return {
        "cmps_interlock": 38.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS <= phase < 44.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS,
        "arc": 82.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS <= phase < 88.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS,
        "ahvps_protection": 118.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS <= phase < 124.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS,
        "ipps_interlock": 145.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS <= phase < 151.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS,
        "degraded": 168.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS <= phase < 173.0 / _REFERENCE_PROBLEM_CYCLE_SECONDS,
    }


def simulation_data_state(
    elapsed: float | None = None,
    problem_cycle_seconds: float = DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS,
) -> DataState:
    elapsed = elapsed_seconds() if elapsed is None else elapsed
    return DataState.DEGRADED if _scenario(elapsed, problem_cycle_seconds)["degraded"] else DataState.LIVE


def _build_telemetry(elapsed: float, timestamp: datetime, data_state: DataState) -> TelemetryPoint:
    return TelemetryPoint(
        timestamp=timestamp,
        source=DataSource.SIMULATION,
        sequence=int(elapsed),
        ionV=_signal(_wave(4.5, 0.18, 24.0, elapsed), "V", timestamp, data_state),
        ionI=_signal(_wave(1.8, 0.09, 29.0, elapsed, 0.8), "A", timestamp, data_state),
        heatV=_signal(_wave(7.0, 0.22, 21.0, elapsed, 0.4), "V", timestamp, data_state),
        heatI=_signal(_wave(3.2, 0.14, 27.0, elapsed, 1.1), "A", timestamp, data_state),
        heLvl=_signal(_wave(68.0, 1.2, 75.0, elapsed, 0.2), "%", timestamp, data_state),
        Thot=_signal(_wave(62.0, 1.1, 41.0, elapsed, 0.6), "degC", timestamp, data_state),
        Tcold=_signal(_wave(28.0, 0.8, 47.0, elapsed, 1.4), "degC", timestamp, data_state),
    )


def _observed_state(state: InterpretedState, data_state: DataState) -> InterpretedState:
    return state if data_state in {DataState.LIVE, DataState.DEGRADED} else InterpretedState.UNKNOWN


def _observed_condition(state: ConditionState, data_state: DataState) -> ConditionState:
    return state if data_state in {DataState.LIVE, DataState.DEGRADED} else ConditionState.UNKNOWN


def _build_equipment(
    elapsed: float,
    timestamp: datetime,
    data_state: DataState,
    scenario: dict[str, bool],
    telemetry: TelemetryPoint,
) -> dict[str, EquipmentStatus]:
    cmps_fault = scenario["cmps_interlock"]
    arc_active = scenario["arc"]
    ahvps_fault = scenario["ahvps_protection"]
    ipps_fault = scenario["ipps_interlock"]
    quality = _quality(data_state)

    def equipment_status(
        state: InterpretedState,
        *,
        feedback: ConditionState | None = None,
        interlock: ConditionState | None = None,
        protection: ConditionState | None = None,
        severity: AlarmSeverity | None = None,
        readings: dict[str, SignalValue] | None = None,
    ) -> EquipmentStatus:
        return EquipmentStatus(
            state=_observed_state(state, data_state),
            quality=quality,
            data_state=data_state,
            feedback=_observed_condition(feedback, data_state) if feedback is not None else None,
            interlock=_observed_condition(interlock, data_state) if interlock is not None else None,
            protection=_observed_condition(protection, data_state) if protection is not None else None,
            severity=severity,
            readings=readings or {},
        )

    return {
        "cmps": equipment_status(
            InterpretedState.FAULT if cmps_fault else InterpretedState.ON,
            feedback=ConditionState.FAULT if cmps_fault else ConditionState.OK,
            interlock=ConditionState.FAULT if cmps_fault else ConditionState.OK,
            readings={"current": _signal(_wave(8.4, 0.22, 32.0, elapsed), "A", timestamp, data_state)},
        ),
        "cfps": equipment_status(
            InterpretedState.ON,
            feedback=ConditionState.OK,
            interlock=ConditionState.OK,
            readings={"power": _signal(_wave(350.0, 7.0, 37.0, elapsed, 0.5), "W", timestamp, data_state)},
        ),
        "ipps": equipment_status(
            InterpretedState.FAULT if ipps_fault else InterpretedState.ON,
            feedback=ConditionState.FAULT if ipps_fault else ConditionState.OK,
            interlock=ConditionState.FAULT if ipps_fault else ConditionState.OK,
            readings={"voltage": telemetry.ionV, "current": telemetry.ionI},
        ),
        "arc_detector": equipment_status(
            InterpretedState.ACTIVE if arc_active else InterpretedState.INACTIVE,
            feedback=ConditionState.FAULT if arc_active else ConditionState.OK,
            severity=AlarmSeverity.CRITICAL,
        ),
        "ahvps": equipment_status(
            InterpretedState.FAULT if ahvps_fault else InterpretedState.ON,
            feedback=ConditionState.FAULT if ahvps_fault else ConditionState.OK,
            interlock=ConditionState.OK,
            protection=ConditionState.FAULT if ahvps_fault else ConditionState.OK,
            readings={"voltage": _signal(_wave(42.0, 0.34, 43.0, elapsed, 0.3), "kV", timestamp, data_state)},
        ),
        "chvps": equipment_status(
            InterpretedState.ON,
            feedback=ConditionState.OK,
            interlock=ConditionState.OK,
            protection=ConditionState.OK,
            readings={"voltage": _signal(_wave(18.0, 0.23, 51.0, elapsed, 1.2), "kV", timestamp, data_state)},
        ),
        "pulse_generator": equipment_status(
            InterpretedState.ON,
            feedback=ConditionState.OK,
            readings={
                "pulse_length": _signal(_wave(2.5, 0.025, 35.0, elapsed, 0.9), "ms", timestamp, data_state),
                "pulse_period": _signal(_wave(1.0, 0.012, 46.0, elapsed, 1.7), "s", timestamp, data_state),
            },
        ),
    }


def _build_state_signals(
    timestamp: datetime,
    data_state: DataState,
    scenario: dict[str, bool],
    equipment: dict[str, EquipmentStatus],
) -> dict[LogicalStateSignal, StateSignalValue]:
    result: dict[LogicalStateSignal, StateSignalValue] = {}
    quality = _quality(data_state)
    equipment_by_signal = {
        LogicalStateSignal.CMPS: EquipmentId.CMPS,
        LogicalStateSignal.IPPS: EquipmentId.IPPS,
        LogicalStateSignal.ARC_DETECTOR: EquipmentId.ARC_DETECTOR,
        LogicalStateSignal.OVERVOLTAGE: EquipmentId.AHVPS,
    }

    for signal in LogicalStateSignal:
        kind = state_signal_kind(signal)
        if kind == StateSignalKind.COMPONENT:
            interpreted = (
                InterpretedState.ON
                if signal.value.endswith((".state", ".rectifier", ".converter"))
                else InterpretedState.OK
            )
        elif kind == StateSignalKind.INTERLOCK:
            interpreted = InterpretedState.OK
        else:
            interpreted = InterpretedState.INACTIVE

        severity = None
        if signal == LogicalStateSignal.CMPS:
            interpreted = InterpretedState.FAULT if scenario["cmps_interlock"] else InterpretedState.OK
            severity = AlarmSeverity.WARNING
        elif signal == LogicalStateSignal.IPPS:
            interpreted = InterpretedState.FAULT if scenario["ipps_interlock"] else InterpretedState.OK
            severity = AlarmSeverity.WARNING
        elif signal == LogicalStateSignal.ARC_DETECTOR:
            interpreted = equipment["arc_detector"].state
            severity = AlarmSeverity.CRITICAL
        elif signal == LogicalStateSignal.OVERVOLTAGE:
            interpreted = InterpretedState.ACTIVE if scenario["ahvps_protection"] else InterpretedState.INACTIVE
            severity = AlarmSeverity.CRITICAL
        elif kind == StateSignalKind.ALARM:
            severity = AlarmSeverity.WARNING

        observed = _observed_state(interpreted, data_state)
        result[signal] = StateSignalValue(
            logical_name=signal.value,
            display_name=state_signal_label(signal),
            group=state_signal_group(signal),
            mapped=True,
            raw_value=(
                None
                if data_state == DataState.UNAVAILABLE
                else interpreted in {InterpretedState.ON, InterpretedState.OK, InterpretedState.ACTIVE}
            ),
            interpreted_state=observed,
            quality=quality,
            source_timestamp=None if data_state == DataState.UNAVAILABLE else timestamp,
            observed_at=timestamp,
            source=DataSource.SIMULATION,
            data_state=data_state,
            severity=severity,
            equipment=equipment_by_signal.get(signal),
        )
    return result


def simulation_snapshot(
    *,
    problem_cycle_seconds: float = DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS,
    elapsed: float | None = None,
    timestamp: datetime | None = None,
    data_state: DataState | None = None,
) -> SimulationSnapshot:
    elapsed = elapsed_seconds() if elapsed is None else max(0.0, elapsed)
    timestamp = timestamp or datetime.now(timezone.utc)
    scenario = _scenario(elapsed, problem_cycle_seconds)
    data_state = data_state or (DataState.DEGRADED if scenario["degraded"] else DataState.LIVE)
    telemetry = _build_telemetry(elapsed, timestamp, data_state)
    equipment = _build_equipment(elapsed, timestamp, data_state, scenario, telemetry)
    state_signals = _build_state_signals(timestamp, data_state, scenario, equipment)
    return SimulationSnapshot(
        timestamp=timestamp,
        elapsed=elapsed,
        data_state=data_state,
        telemetry=telemetry,
        equipment=equipment,
        state_signals=state_signals,
    )


def simulation_telemetry(
    *,
    problem_cycle_seconds: float = DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS,
) -> TelemetryPoint:
    return simulation_snapshot(problem_cycle_seconds=problem_cycle_seconds).telemetry


def simulation_equipment(
    elapsed: float | None = None,
    *,
    problem_cycle_seconds: float = DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS,
    data_state: DataState | None = None,
) -> dict[str, EquipmentStatus]:
    return simulation_snapshot(
        problem_cycle_seconds=problem_cycle_seconds,
        elapsed=elapsed,
        data_state=data_state,
    ).equipment


def simulation_state_signals(
    data_state: DataState,
    *,
    problem_cycle_seconds: float = DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS,
) -> dict[LogicalStateSignal, StateSignalValue]:
    return simulation_snapshot(
        problem_cycle_seconds=problem_cycle_seconds,
        data_state=data_state,
    ).state_signals


def seed_simulation_events(store: EventStore) -> int:
    try:
        if store.query(limit=1, event_type=f"{SIMULATION_SEED_VERSION}.marker"):
            return 0
    except EventStoreUnavailable:
        return 0

    now = datetime.now(timezone.utc)
    correlation_id = SIMULATION_SEED_VERSION
    seeds = [
        EventCreate(recorded_at=now - timedelta(minutes=11), category=EventCategory.INTERLOCK, event_type=f"{SIMULATION_SEED_VERSION}.cmps", source="simulation", severity=AlarmSeverity.WARNING, equipment=EquipmentId.CMPS, state=EventState.RECOVERED, target="interlock.cmps", message="CMPS supply interlock recovered", details={"from": "fault", "to": "ok"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=9), category=EventCategory.MONITORING, event_type=f"{SIMULATION_SEED_VERSION}.cfps", source="simulation", severity=AlarmSeverity.WARNING, equipment=EquipmentId.CFPS, state=EventState.RECOVERED, target="cfps.feedback", message="CFPS feedback returned to operating range", details={"from": "warning", "to": "ok"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=7), category=EventCategory.ALARM, event_type=f"{SIMULATION_SEED_VERSION}.arc_active", source="simulation", severity=AlarmSeverity.CRITICAL, equipment=EquipmentId.ARC_DETECTOR, state=EventState.ACTIVE, target="alarm.arc_detector", message="ARC detector activated", details={"from": "inactive", "to": "active"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=6), category=EventCategory.ALARM, event_type=f"{SIMULATION_SEED_VERSION}.arc_clear", source="simulation", severity=AlarmSeverity.CRITICAL, equipment=EquipmentId.ARC_DETECTOR, state=EventState.RECOVERED, target="alarm.arc_detector", message="ARC detector cleared", details={"from": "active", "to": "inactive"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=4), category=EventCategory.MACHINE_STATE, event_type=f"{SIMULATION_SEED_VERSION}.ahvps", source="simulation", severity=AlarmSeverity.WARNING, equipment=EquipmentId.AHVPS, state=EventState.RECOVERED, target="ahvps.protection", message="AHVPS protection warning cleared", details={"from": "fault", "to": "ok"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=2), category=EventCategory.MACHINE_STATE, event_type=f"{SIMULATION_SEED_VERSION}.chvps", source="simulation", severity=AlarmSeverity.CRITICAL, equipment=EquipmentId.CHVPS, state=EventState.RECOVERED, target="chvps.protection", message="CHVPS overvoltage protection recovered", details={"from": "fault", "to": "ok"}, correlation_id=correlation_id),
    ]
    inserted = sum(store.append(event) is not None for event in seeds)
    marker = EventCreate(
        category=EventCategory.APPLICATION,
        event_type=f"{SIMULATION_SEED_VERSION}.marker",
        source="simulation",
        equipment=EquipmentId.SYSTEM,
        message="Simulation UX history seed initialized",
        details={"seed_version": SIMULATION_SEED_VERSION, "problem_events": inserted},
        correlation_id=correlation_id,
    )
    store.append(marker)
    return inserted
