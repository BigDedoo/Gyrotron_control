from datetime import datetime, timezone

from app.core.config import AppSettings
from app.events.models import EventState
from app.events.store import EventStore
from app.models import (
    AlarmSeverity,
    DataState,
    DataSource,
    EquipmentId,
    InterpretedState,
    SignalQuality,
)
from app.opcua.node_map import LogicalStateSignal
from app.simulation import (
    DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS,
    seed_simulation_events,
    simulation_snapshot,
    simulation_state_signals,
)


def test_simulation_problem_seed_is_idempotent_and_explicit(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")

    assert seed_simulation_events(store) == 6
    assert seed_simulation_events(store) == 0

    warnings = store.query(limit=20, severity=AlarmSeverity.WARNING)
    criticals = store.query(limit=20, severity=AlarmSeverity.CRITICAL)
    problems = [*warnings, *criticals]
    assert warnings and criticals
    assert all(event.source == "simulation" for event in problems)
    assert all(event.equipment is not None for event in problems)
    assert all(
        event.state == EventState.RECOVERED
        for event in problems
        if "arc_active" not in event.event_type
    )
    assert (
        next(event for event in problems if "arc_active" in event.event_type).state
        == EventState.ACTIVE
    )


def test_simulation_state_signals_are_backend_authoritative(monkeypatch):
    monkeypatch.setattr("app.simulation.elapsed_seconds", lambda: 83.0)
    signals = simulation_state_signals(DataState.LIVE, problem_cycle_seconds=180.0)

    arc = signals[LogicalStateSignal.ARC_DETECTOR]
    assert arc.source == DataSource.SIMULATION
    assert arc.mapped is True
    assert arc.interpreted_state == InterpretedState.ACTIVE
    assert arc.severity == AlarmSeverity.CRITICAL
    assert arc.equipment == EquipmentId.ARC_DETECTOR


def test_degraded_simulation_quality_propagates_without_inventing_faults():
    snapshot = simulation_snapshot(elapsed=10.0, data_state=DataState.DEGRADED)

    assert snapshot.data_state == DataState.DEGRADED
    assert all(
        item.data_state == DataState.DEGRADED for item in snapshot.equipment.values()
    )
    assert all(
        item.quality == SignalQuality.UNCERTAIN for item in snapshot.equipment.values()
    )
    assert all(
        item.state != InterpretedState.FAULT for item in snapshot.equipment.values()
    )
    assert all(
        reading.quality == SignalQuality.UNCERTAIN
        for item in snapshot.equipment.values()
        for reading in item.readings.values()
    )


def test_stale_and_unavailable_equipment_are_not_presented_as_current():
    stale = simulation_snapshot(elapsed=10.0, data_state=DataState.STALE)
    unavailable = simulation_snapshot(elapsed=10.0, data_state=DataState.UNAVAILABLE)

    assert all(
        item.state == InterpretedState.UNKNOWN for item in stale.equipment.values()
    )
    assert all(
        item.quality == SignalQuality.UNCERTAIN for item in stale.equipment.values()
    )
    assert all(
        reading.value is not None and reading.quality == SignalQuality.UNCERTAIN
        for item in stale.equipment.values()
        for reading in item.readings.values()
    )
    assert all(
        item.state == InterpretedState.UNKNOWN
        for item in unavailable.equipment.values()
    )
    assert all(
        item.quality == SignalQuality.UNAVAILABLE
        for item in unavailable.equipment.values()
    )
    assert all(
        reading.value is None and reading.source_timestamp is None
        for item in unavailable.equipment.values()
        for reading in item.readings.values()
    )


def test_simulation_snapshot_uses_one_timestamp_and_ipps_readings():
    timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    snapshot = simulation_snapshot(elapsed=12.5, timestamp=timestamp)

    assert snapshot.timestamp == timestamp
    assert snapshot.telemetry.timestamp == timestamp
    assert snapshot.equipment["ipps"].readings["voltage"] == snapshot.telemetry.ionV
    assert snapshot.equipment["ipps"].readings["current"] == snapshot.telemetry.ionI
    assert all(
        signal.observed_at == timestamp for signal in snapshot.state_signals.values()
    )


def test_problem_cycle_default_is_fifteen_minutes_and_can_be_overridden():
    assert DEFAULT_SIMULATION_PROBLEM_CYCLE_SECONDS == 900.0
    fast = simulation_snapshot(elapsed=40.0, problem_cycle_seconds=180.0)
    default = simulation_snapshot(elapsed=40.0)
    normalized_default = simulation_snapshot(elapsed=200.0)

    assert fast.equipment["cmps"].state == InterpretedState.FAULT
    assert default.equipment["cmps"].state == InterpretedState.ON
    assert normalized_default.equipment["cmps"].state == InterpretedState.FAULT


def test_problem_cycle_environment_setting_defaults_and_overrides(monkeypatch):
    monkeypatch.setenv("APP_MODE", "simulation")
    monkeypatch.delenv("SIMULATION_PROBLEM_CYCLE_SECONDS", raising=False)
    assert AppSettings.from_environment().simulation_problem_cycle_seconds == 900.0

    monkeypatch.setenv("SIMULATION_PROBLEM_CYCLE_SECONDS", "120")
    assert AppSettings.from_environment().simulation_problem_cycle_seconds == 120.0
