import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.events.models import EventCategory, EventCreate, EventRecord, EventState
from app.models import AlarmSeverity, EquipmentId


logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class EventStoreUnavailable(RuntimeError):
    pass


class EventStore:
    """Append-oriented SQLite history with no application update/delete surface."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self._lock = threading.RLock()
        self.available = False
        self.last_error: str | None = None
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=3)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recorded_at TEXT NOT NULL,
                        source_timestamp TEXT,
                        category TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        source TEXT NOT NULL,
                        severity TEXT,
                        equipment TEXT,
                        state TEXT,
                        actor TEXT,
                        target TEXT,
                        message TEXT NOT NULL,
                        details_json TEXT NOT NULL,
                        correlation_id TEXT
                    )
                    """
                )
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(events)").fetchall()
                }
                if "equipment" not in columns:
                    connection.execute("ALTER TABLE events ADD COLUMN equipment TEXT")
                if "state" not in columns:
                    connection.execute("ALTER TABLE events ADD COLUMN state TEXT")
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_events_category_id ON events(category, id DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_events_type_id ON events(event_type, id DESC)"
                )
            self.available = True
            self.last_error = None
        except (OSError, sqlite3.Error) as exc:
            self.available = False
            self.last_error = "Event history storage is unavailable"
            logger.error("Event store initialization failed (%s)", type(exc).__name__)

    def append(self, event: EventCreate) -> EventRecord | None:
        if not self.available:
            logger.error("Event was not recorded because event history is unavailable")
            return None
        recorded_at = _as_utc(event.recorded_at or datetime.now(timezone.utc))
        source_timestamp = (
            _as_utc(event.source_timestamp)
            if event.source_timestamp is not None
            else None
        )
        try:
            details = event.model_dump(mode="json")["details"]
            details_json = json.dumps(details, sort_keys=True, separators=(",", ":"))
            with self._lock, self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO events (
                        recorded_at, source_timestamp, category, event_type, source,
                        severity, equipment, state, actor, target, message, details_json,
                        correlation_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recorded_at.isoformat(),
                        source_timestamp.isoformat() if source_timestamp else None,
                        event.category.value,
                        event.event_type,
                        event.source,
                        event.severity.value if event.severity else None,
                        event.equipment.value if event.equipment else None,
                        event.state.value if event.state else None,
                        event.actor,
                        event.target,
                        event.message,
                        details_json,
                        event.correlation_id,
                    ),
                )
                event_id = int(cursor.lastrowid)
            return EventRecord(
                id=event_id,
                recorded_at=recorded_at,
                source_timestamp=source_timestamp,
                category=event.category,
                event_type=event.event_type,
                source=event.source,
                severity=event.severity,
                equipment=event.equipment,
                state=event.state,
                actor=event.actor,
                target=event.target,
                message=event.message,
                details=details,
                correlation_id=event.correlation_id,
            )
        except (TypeError, ValueError, OSError, sqlite3.Error) as exc:
            self.available = False
            self.last_error = "Event history storage is unavailable"
            logger.error("Event store append failed (%s)", type(exc).__name__)
            return None

    def query(
        self,
        *,
        limit: int,
        before_id: int | None = None,
        category: EventCategory | None = None,
        severity: AlarmSeverity | None = None,
        event_type: str | None = None,
        actor: str | None = None,
    ) -> list[EventRecord]:
        if not self.available:
            raise EventStoreUnavailable(self.last_error or "Event history is unavailable")
        if limit < 1 or limit > 201:
            raise ValueError("Event query limit must be between 1 and 201")
        if before_id is not None and before_id < 1:
            raise ValueError("before_id must be positive")
        conditions: list[str] = []
        parameters: list[object] = []
        if before_id is not None:
            conditions.append("id < ?")
            parameters.append(before_id)
        if category is not None:
            conditions.append("category = ?")
            parameters.append(category.value)
        if severity is not None:
            conditions.append("severity = ?")
            parameters.append(severity.value)
        if event_type is not None:
            conditions.append("event_type = ?")
            parameters.append(event_type)
        if actor is not None:
            conditions.append("actor = ?")
            parameters.append(actor)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        try:
            with self._lock, self._connect() as connection:
                rows = connection.execute(
                    f"SELECT * FROM events{where} ORDER BY id DESC LIMIT ?",  # noqa: S608
                    parameters,
                ).fetchall()
        except (OSError, sqlite3.Error) as exc:
            self.available = False
            self.last_error = "Event history storage is unavailable"
            logger.error("Event store query failed (%s)", type(exc).__name__)
            raise EventStoreUnavailable(self.last_error) from exc
        return [self._record(row) for row in rows]

    @staticmethod
    def _record(row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            id=row["id"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            source_timestamp=(
                datetime.fromisoformat(row["source_timestamp"])
                if row["source_timestamp"]
                else None
            ),
            category=EventCategory(row["category"]),
            event_type=row["event_type"],
            source=row["source"],
            severity=AlarmSeverity(row["severity"]) if row["severity"] else None,
            equipment=EquipmentId(row["equipment"]) if row["equipment"] else None,
            state=EventState(row["state"]) if row["state"] else None,
            actor=row["actor"],
            target=row["target"],
            message=row["message"],
            details=json.loads(row["details_json"]),
            correlation_id=row["correlation_id"],
        )
