import math
import time
from datetime import datetime, timedelta, timezone

from app.events.models import EventCategory, EventCreate
from app.events.store import EventStore, EventStoreUnavailable
from app.models import (
    AlarmSeverity,
    ConditionState,
    DataSource,
    DataState,
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
_started_at = time.monotonic()


def elapsed_seconds() -> float:
    return max(0.0, time.monotonic() - _started_at)


def _wave(base: float, amplitude: float, period: float, elapsed: float, phase: float = 0.0) -> float:
    slow = math.sin((elapsed / period) * math.tau + phase)
    texture = math.sin((elapsed / (period / 4.7)) * math.tau + phase / 2) * 0.12
    return base + amplitude * (slow + texture)


def _signal(value: float, unit: str, timestamp: datetime, quality: SignalQuality = SignalQuality.GOOD) -> SignalValue:
    return SignalValue(
        value=round(value, 3),
        unit=unit,
        quality=quality,
        source_timestamp=timestamp,
    )


def _scenario(elapsed: float) -> dict[str, bool]:
    phase = elapsed % 180.0
    return {
        "cmps_interlock": 38.0 <= phase < 44.0,
        "arc": 82.0 <= phase < 88.0,
        "ahvps_protection": 118.0 <= phase < 124.0,
        "ipps_interlock": 145.0 <= phase < 151.0,
        "degraded": 168.0 <= phase < 173.0,
    }


def simulation_data_state(elapsed: float | None = None) -> DataState:
    elapsed = elapsed_seconds() if elapsed is None else elapsed
    return DataState.DEGRADED if _scenario(elapsed)["degraded"] else DataState.LIVE


def simulation_telemetry() -> TelemetryPoint:
    elapsed = elapsed_seconds()
    timestamp = datetime.now(timezone.utc)
    degraded = _scenario(elapsed)["degraded"]
    ion_quality = SignalQuality.UNCERTAIN if degraded else SignalQuality.GOOD
    return TelemetryPoint(
        timestamp=timestamp,
        source=DataSource.SIMULATION,
        sequence=int(elapsed),
        ionV=_signal(_wave(4.5, 0.18, 24.0, elapsed), "V", timestamp, ion_quality),
        ionI=_signal(_wave(1.8, 0.09, 29.0, elapsed, 0.8), "A", timestamp, ion_quality),
        heatV=_signal(_wave(7.0, 0.22, 21.0, elapsed, 0.4), "V", timestamp),
        heatI=_signal(_wave(3.2, 0.14, 27.0, elapsed, 1.1), "A", timestamp),
        heLvl=_signal(_wave(68.0, 1.2, 75.0, elapsed, 0.2), "%", timestamp),
        Thot=_signal(_wave(62.0, 1.1, 41.0, elapsed, 0.6), "degC", timestamp),
        Tcold=_signal(_wave(28.0, 0.8, 47.0, elapsed, 1.4), "degC", timestamp),
    )


def simulation_equipment(elapsed: float | None = None) -> dict[str, EquipmentStatus]:
    elapsed = elapsed_seconds() if elapsed is None else elapsed
    timestamp = datetime.now(timezone.utc)
    scenario = _scenario(elapsed)
    telemetry = simulation_telemetry()
    cmps_fault = scenario["cmps_interlock"]
    arc_active = scenario["arc"]
    ahvps_fault = scenario["ahvps_protection"]
    ipps_fault = scenario["ipps_interlock"]

    return {
        "cmps": EquipmentStatus(
            state=InterpretedState.FAULT if cmps_fault else InterpretedState.ON,
            quality=SignalQuality.GOOD,
            feedback=ConditionState.FAULT if cmps_fault else ConditionState.OK,
            interlock=ConditionState.FAULT if cmps_fault else ConditionState.OK,
            readings={"current": _signal(_wave(8.4, 0.22, 32.0, elapsed), "A", timestamp)},
        ),
        "cfps": EquipmentStatus(
            state=InterpretedState.ON,
            quality=SignalQuality.GOOD,
            feedback=ConditionState.OK,
            interlock=ConditionState.OK,
            readings={"power": _signal(_wave(350.0, 7.0, 37.0, elapsed, 0.5), "W", timestamp)},
        ),
        "ipps": EquipmentStatus(
            state=InterpretedState.FAULT if ipps_fault else InterpretedState.ON,
            quality=telemetry.ionV.quality,
            feedback=ConditionState.FAULT if ipps_fault else ConditionState.OK,
            interlock=ConditionState.FAULT if ipps_fault else ConditionState.OK,
            readings={"voltage": telemetry.ionV, "current": telemetry.ionI},
        ),
        "arc_detector": EquipmentStatus(
            state=InterpretedState.ACTIVE if arc_active else InterpretedState.INACTIVE,
            quality=SignalQuality.GOOD,
            feedback=ConditionState.FAULT if arc_active else ConditionState.OK,
            severity=AlarmSeverity.CRITICAL,
        ),
        "ahvps": EquipmentStatus(
            state=InterpretedState.FAULT if ahvps_fault else InterpretedState.ON,
            quality=SignalQuality.GOOD,
            feedback=ConditionState.FAULT if ahvps_fault else ConditionState.OK,
            interlock=ConditionState.OK,
            protection=ConditionState.FAULT if ahvps_fault else ConditionState.OK,
            readings={"voltage": _signal(_wave(42.0, 0.34, 43.0, elapsed, 0.3), "kV", timestamp)},
        ),
        "chvps": EquipmentStatus(
            state=InterpretedState.ON,
            quality=SignalQuality.GOOD,
            feedback=ConditionState.OK,
            interlock=ConditionState.OK,
            protection=ConditionState.OK,
            readings={"voltage": _signal(_wave(18.0, 0.23, 51.0, elapsed, 1.2), "kV", timestamp)},
        ),
        "pulse_generator": EquipmentStatus(
            state=InterpretedState.ON,
            quality=SignalQuality.GOOD,
            feedback=ConditionState.OK,
            readings={
                "pulse_length": _signal(_wave(2.5, 0.025, 35.0, elapsed, 0.9), "ms", timestamp),
                "pulse_period": _signal(_wave(1.0, 0.012, 46.0, elapsed, 1.7), "s", timestamp),
            },
        ),
    }


def simulation_state_signals(data_state: DataState) -> dict[LogicalStateSignal, StateSignalValue]:
    elapsed = elapsed_seconds()
    timestamp = datetime.now(timezone.utc)
    scenario = _scenario(elapsed)
    equipment = simulation_equipment(elapsed)
    result: dict[LogicalStateSignal, StateSignalValue] = {}

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

        result[signal] = StateSignalValue(
            logical_name=signal.value,
            display_name=state_signal_label(signal),
            group=state_signal_group(signal),
            mapped=True,
            raw_value=interpreted in {InterpretedState.ON, InterpretedState.OK, InterpretedState.ACTIVE},
            interpreted_state=interpreted,
            quality=SignalQuality.GOOD if data_state == DataState.LIVE else SignalQuality.UNCERTAIN,
            source_timestamp=timestamp,
            observed_at=timestamp,
            source=DataSource.SIMULATION,
            data_state=data_state,
            severity=severity,
        )
    return result


def seed_simulation_events(store: EventStore) -> int:
    try:
        if store.query(limit=1, event_type=f"{SIMULATION_SEED_VERSION}.marker"):
            return 0
    except EventStoreUnavailable:
        return 0

    now = datetime.now(timezone.utc)
    correlation_id = SIMULATION_SEED_VERSION
    seeds = [
        EventCreate(recorded_at=now - timedelta(minutes=11), category=EventCategory.INTERLOCK, event_type=f"{SIMULATION_SEED_VERSION}.cmps", source="simulation", severity=AlarmSeverity.WARNING, target="interlock.cmps", message="CMPS supply interlock recovered", details={"from": "fault", "to": "ok"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=9), category=EventCategory.MONITORING, event_type=f"{SIMULATION_SEED_VERSION}.cfps", source="simulation", severity=AlarmSeverity.WARNING, target="cfps.feedback", message="CFPS feedback briefly deviated from operating range", details={"from": "warning", "to": "ok"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=7), category=EventCategory.ALARM, event_type=f"{SIMULATION_SEED_VERSION}.arc_active", source="simulation", severity=AlarmSeverity.CRITICAL, target="alarm.arc_detector", message="ARC detector activated", details={"from": "inactive", "to": "active"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=6), category=EventCategory.ALARM, event_type=f"{SIMULATION_SEED_VERSION}.arc_clear", source="simulation", severity=AlarmSeverity.CRITICAL, target="alarm.arc_detector", message="ARC detector returned inactive", details={"from": "active", "to": "inactive"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=4), category=EventCategory.MACHINE_STATE, event_type=f"{SIMULATION_SEED_VERSION}.ahvps", source="simulation", severity=AlarmSeverity.WARNING, target="ahvps.protection", message="AHVPS protection warning cleared", details={"from": "fault", "to": "ok"}, correlation_id=correlation_id),
        EventCreate(recorded_at=now - timedelta(minutes=2), category=EventCategory.MACHINE_STATE, event_type=f"{SIMULATION_SEED_VERSION}.chvps", source="simulation", severity=AlarmSeverity.CRITICAL, target="chvps.protection", message="CHVPS overvoltage protection recovered", details={"from": "fault", "to": "ok"}, correlation_id=correlation_id),
    ]
    inserted = sum(store.append(event) is not None for event in seeds)
    marker = EventCreate(
        category=EventCategory.APPLICATION,
        event_type=f"{SIMULATION_SEED_VERSION}.marker",
        source="simulation",
        message="Simulation UX history seed initialized",
        details={"seed_version": SIMULATION_SEED_VERSION, "problem_events": inserted},
        correlation_id=correlation_id,
    )
    store.append(marker)
    return inserted
