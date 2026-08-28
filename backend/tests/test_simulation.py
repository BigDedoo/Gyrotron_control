from app.events.store import EventStore
from app.models import AlarmSeverity, DataState, DataSource, InterpretedState
from app.simulation import seed_simulation_events, simulation_state_signals
from app.opcua.node_map import LogicalStateSignal


def test_simulation_problem_seed_is_idempotent_and_explicit(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")

    assert seed_simulation_events(store) == 6
    assert seed_simulation_events(store) == 0

    warnings = store.query(limit=20, severity=AlarmSeverity.WARNING)
    criticals = store.query(limit=20, severity=AlarmSeverity.CRITICAL)
    assert warnings and criticals
    assert all(event.source == "simulation" for event in [*warnings, *criticals])


def test_simulation_state_signals_are_backend_authoritative(monkeypatch):
    monkeypatch.setattr("app.simulation.elapsed_seconds", lambda: 83.0)
    signals = simulation_state_signals(DataState.LIVE)

    arc = signals[LogicalStateSignal.ARC_DETECTOR]
    assert arc.source == DataSource.SIMULATION
    assert arc.mapped is True
    assert arc.interpreted_state == InterpretedState.ACTIVE
    assert arc.severity == AlarmSeverity.CRITICAL
