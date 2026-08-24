from datetime import datetime, timezone

from app.events.models import EventCategory, EventCreate
from app.events.store import EventStore
from app.models import AlarmSeverity


def test_event_store_initializes_appends_and_survives_recreation(tmp_path):
    path = tmp_path / "events.sqlite3"
    store = EventStore(path)
    assert store.available
    created = store.append(
        EventCreate(
            recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            category=EventCategory.APPLICATION,
            event_type="application.test",
            source="test",
            message="Persistent event",
            details={"sequence": 1},
        )
    )
    assert created is not None

    reopened = EventStore(path)
    events = reopened.query(limit=10)
    assert [event.id for event in events] == [created.id]
    assert events[0].message == "Persistent event"
    assert events[0].details == {"sequence": 1}


def test_event_query_is_deterministic_bounded_paginated_and_filtered(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    for index in range(6):
        store.append(
            EventCreate(
                category=EventCategory.ALARM if index % 2 else EventCategory.MONITORING,
                event_type="alarm.changed" if index % 2 else "monitor.changed",
                source="test",
                severity=AlarmSeverity.CRITICAL if index == 5 else None,
                actor="operator" if index == 3 else None,
                message=f"Event {index}",
            )
        )

    first_page = store.query(limit=2)
    assert [event.message for event in first_page] == ["Event 5", "Event 4"]
    second_page = store.query(limit=2, before_id=first_page[-1].id)
    assert [event.message for event in second_page] == ["Event 3", "Event 2"]
    assert all(event.category == EventCategory.ALARM for event in store.query(limit=10, category=EventCategory.ALARM))
    assert [event.message for event in store.query(limit=10, severity=AlarmSeverity.CRITICAL)] == ["Event 5"]
    assert [event.message for event in store.query(limit=10, actor="operator")] == ["Event 3"]
    assert [event.message for event in store.query(limit=10, event_type="monitor.changed")] == ["Event 4", "Event 2", "Event 0"]
    try:
        store.query(limit=202)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("unbounded event query was accepted")


def test_event_store_has_no_application_update_or_delete_operations(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    assert not hasattr(store, "update")
    assert not hasattr(store, "delete")
    assert {"append", "query"}.issubset(dir(store))


def test_event_store_failure_is_nonfatal_to_callers(tmp_path):
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("occupied", encoding="utf-8")
    store = EventStore(parent_file / "events.sqlite3")
    assert not store.available
    assert store.append(
        EventCreate(
            category=EventCategory.APPLICATION,
            event_type="application.test",
            source="test",
            message="Cannot persist",
        )
    ) is None
