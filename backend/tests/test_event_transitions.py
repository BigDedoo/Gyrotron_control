from datetime import datetime, timezone

from app.events.detector import EventTransitionDetector
from app.events.models import EventCategory, EventState
from app.events.store import EventStore
from app.models import (
    AlarmMonitoringState,
    AlarmSeverity,
    AlarmSummary,
    AppMode,
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
    StateSignalValue,
    SystemStatus,
)


def _component() -> ComponentStatus:
    return ComponentStatus(
        state=ComponentState.UNKNOWN,
        ready=ConditionState.UNKNOWN,
        rectifier=ComponentState.UNKNOWN,
        converter=ComponentState.UNKNOWN,
        protection=ConditionState.UNKNOWN,
        signals={},
    )


def _signal(
    name: str,
    label: str,
    interpreted: InterpretedState,
    *,
    data_state: DataState = DataState.LIVE,
    severity: AlarmSeverity | None = None,
    equipment: EquipmentId | None = None,
) -> StateSignalValue:
    return StateSignalValue(
        logical_name=name,
        display_name=label,
        group="test",
        mapped=True,
        raw_value=interpreted in {InterpretedState.OK, InterpretedState.ACTIVE},
        interpreted_state=interpreted,
        quality=SignalQuality.GOOD if data_state == DataState.LIVE else SignalQuality.UNAVAILABLE,
        source_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        observed_at=datetime.now(timezone.utc),
        source=DataSource.OPCUA,
        data_state=data_state,
        severity=severity,
        equipment=equipment,
    )


def _status(
    *,
    connection: ConnectionState = ConnectionState.CONNECTED,
    data_state: DataState = DataState.LIVE,
    interlock: InterpretedState = InterpretedState.OK,
    alarm: InterpretedState = InterpretedState.INACTIVE,
    overall: OverallState = OverallState.UNKNOWN,
) -> SystemStatus:
    signal_state = DataState.LIVE if data_state in {DataState.LIVE, DataState.DEGRADED} else data_state
    interlock_signal = _signal(
        "interlock.cmps",
        "CMPS",
        interlock,
        data_state=signal_state,
        equipment=EquipmentId.CMPS,
    )
    alarm_signal = _signal(
        "alarm.arc_detector",
        "ARC detector",
        alarm,
        data_state=signal_state,
        severity=AlarmSeverity.CRITICAL,
        equipment=EquipmentId.ARC_DETECTOR,
    )
    return SystemStatus(
        mode=AppMode.OPCUA_READONLY,
        source=DataSource.OPCUA,
        connection_state=connection,
        data_state=data_state,
        overall_state=overall,
        cps=_component(),
        aps=_component(),
        interlocks=[
            InterlockStatus(
                logical_name=interlock_signal.logical_name,
                group="Environment",
                name=interlock_signal.display_name,
                state=ConditionState.UNKNOWN,
                signal=interlock_signal,
            )
        ],
        alarms=AlarmSummary(
            state=ConditionState.UNKNOWN,
            monitoring_state=AlarmMonitoringState.INCOMPLETE,
            active=[],
            signals=[alarm_signal],
        ),
        coverage=MappingCoverage(total=25, mapped=2, trustworthy=2, complete=False, missing=[]),
        timestamp=datetime.now(timezone.utc),
    )


def _events(store: EventStore):
    return list(reversed(store.query(limit=200)))


def test_first_snapshot_is_baseline_and_unchanged_status_is_deduplicated(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    detector = EventTransitionDetector(store)
    status = _status()
    detector.observe(status)
    for _ in range(20):
        detector.observe(status)
    events = _events(store)
    assert [event.event_type for event in events] == ["monitor.baseline"]


def test_interlock_alarm_and_overall_transitions_are_recorded_once(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    detector = EventTransitionDetector(store)
    detector.observe(_status())
    detector.observe(_status(interlock=InterpretedState.FAULT))
    detector.observe(_status(interlock=InterpretedState.FAULT))
    detector.observe(_status(interlock=InterpretedState.OK))
    detector.observe(_status(alarm=InterpretedState.ACTIVE, overall=OverallState.FAULT))
    detector.observe(_status(alarm=InterpretedState.INACTIVE, overall=OverallState.FAULT))

    events = _events(store)
    interlocks = [event for event in events if event.category == EventCategory.INTERLOCK]
    alarms = [event for event in events if event.category == EventCategory.ALARM]
    assert [(event.details["from"], event.details["to"]) for event in interlocks] == [
        ("ok", "fault"),
        ("fault", "ok"),
    ]
    assert [event.event_type for event in alarms] == ["alarm.activated", "alarm.cleared"]
    assert all(event.severity == AlarmSeverity.CRITICAL for event in alarms)
    assert [event.state for event in interlocks] == [
        EventState.ACTIVE,
        EventState.RECOVERED,
    ]
    assert all(event.severity == AlarmSeverity.WARNING for event in interlocks)
    assert all(event.equipment == EquipmentId.CMPS for event in interlocks)
    assert [event.state for event in alarms] == [
        EventState.ACTIVE,
        EventState.RECOVERED,
    ]
    assert all(event.equipment == EquipmentId.ARC_DETECTOR for event in alarms)
    assert any(event.event_type == "overall_state.changed" for event in events)


def test_communication_gap_logs_one_loss_and_no_fake_physical_transitions(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    detector = EventTransitionDetector(store)
    detector.observe(_status())
    disconnected = _status(
        connection=ConnectionState.DISCONNECTED,
        data_state=DataState.STALE,
        interlock=InterpretedState.UNKNOWN,
        alarm=InterpretedState.UNKNOWN,
    )
    detector.observe(disconnected)
    detector.observe(disconnected)
    detector.observe(
        _status(
            connection=ConnectionState.ERROR,
            data_state=DataState.UNAVAILABLE,
            interlock=InterpretedState.UNKNOWN,
            alarm=InterpretedState.UNKNOWN,
        )
    )
    events = _events(store)
    assert sum(event.event_type == "monitor.connection_lost" for event in events) == 1
    assert not any(event.category in {EventCategory.INTERLOCK, EventCategory.ALARM} for event in events)


def test_recovery_records_observed_after_gap_without_claiming_change_time(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    detector = EventTransitionDetector(store)
    detector.observe(_status())
    detector.observe(
        _status(
            connection=ConnectionState.DISCONNECTED,
            data_state=DataState.STALE,
            interlock=InterpretedState.UNKNOWN,
            alarm=InterpretedState.UNKNOWN,
        )
    )
    detector.observe(_status(interlock=InterpretedState.FAULT))
    events = _events(store)
    assert sum(event.event_type == "monitor.recovered" for event in events) == 1
    changed = next(event for event in events if event.category == EventCategory.INTERLOCK)
    assert changed.details["observed_after_gap"] is True
    assert changed.details["change_time_known"] is False
    assert "after communication gap" in changed.message


def test_data_state_problem_severity_is_source_independent_and_recovery_is_explicit(
    tmp_path,
):
    store = EventStore(tmp_path / "events.sqlite3")
    detector = EventTransitionDetector(store)
    detector.observe(_status())
    detector.observe(_status(data_state=DataState.DEGRADED))
    detector.observe(_status(data_state=DataState.LIVE))

    events = [
        event
        for event in _events(store)
        if event.event_type.startswith("monitor.data_")
    ]
    assert [event.severity for event in events] == [
        AlarmSeverity.WARNING,
        AlarmSeverity.WARNING,
    ]
    assert [event.state for event in events] == [
        EventState.ACTIVE,
        EventState.RECOVERED,
    ]
    assert all(event.equipment == EquipmentId.SYSTEM for event in events)
