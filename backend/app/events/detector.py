import asyncio
import logging

from app.core.config import AppSettings
from app.core.system_status import get_system_status
from app.events.models import EventCategory, EventCreate, EventState
from app.events.store import EventStore
from app.models import (
    AlarmSeverity,
    ConnectionState,
    DataState,
    EquipmentId,
    InterpretedState,
    OverallState,
    SignalQuality,
    StateSignalValue,
    SystemStatus,
)
from app.opcua.monitor import OPCUAMonitor


logger = logging.getLogger(__name__)


class EventTransitionDetector:
    """Converts changes in the authoritative cached status into deduplicated events."""

    def __init__(self, store: EventStore) -> None:
        self.store = store
        self._initialized = False
        self._was_connected = False
        self._ever_connected = False
        self._previous_data_state: DataState | None = None
        self._previous_error: str | None = None
        self._previous_overall: OverallState | None = None
        self._trusted_states: dict[str, InterpretedState] = {}
        self._gapped_signals: set[str] = set()
        self._communication_gap = False

    @staticmethod
    def _signals(status: SystemStatus) -> dict[str, StateSignalValue]:
        signals: dict[str, StateSignalValue] = {}
        for component in (status.cps, status.aps):
            for sample in component.signals.values():
                signals[sample.logical_name] = sample
        for interlock in status.interlocks:
            signals[interlock.logical_name] = interlock.signal
        for alarm in status.alarms.signals:
            signals[alarm.logical_name] = alarm
        return signals

    @staticmethod
    def _trustworthy(sample: StateSignalValue) -> bool:
        return (
            sample.mapped
            and sample.data_state == DataState.LIVE
            and sample.quality == SignalQuality.GOOD
            and sample.interpreted_state != InterpretedState.UNKNOWN
        )

    def observe(self, status: SystemStatus) -> None:
        signals = self._signals(status)
        connected = status.connection_state in {ConnectionState.CONNECTED, ConnectionState.SIMULATED}
        if not self._initialized:
            self._initialized = True
            self._was_connected = connected
            self._ever_connected = connected
            self._previous_data_state = status.data_state
            self._previous_error = status.monitor_error
            self._previous_overall = status.overall_state
            self._trusted_states = {
                name: sample.interpreted_state
                for name, sample in signals.items()
                if self._trustworthy(sample)
            }
            self.store.append(
                EventCreate(
                    category=EventCategory.MONITORING,
                    event_type="monitor.baseline",
                    source=status.source.value,
                    equipment=EquipmentId.SYSTEM,
                    message=(
                        "Simulation monitoring baseline established"
                        if status.source.value == "simulation"
                        else "OPC UA monitoring baseline established"
                    ),
                    details={
                        "mapped": status.coverage.mapped,
                        "trustworthy": status.coverage.trustworthy,
                        "total": status.coverage.total,
                    },
                )
            )
            return

        self._observe_connection(status, connected)
        self._observe_data_state(status)
        self._observe_monitor_error(status)
        self._observe_machine_signals(signals)
        self._observe_overall(status)
        self._was_connected = connected

    def _observe_connection(self, status: SystemStatus, connected: bool) -> None:
        if self._was_connected and not connected:
            self._communication_gap = True
            self.store.append(
                EventCreate(
                    category=EventCategory.MONITORING,
                    event_type="monitor.connection_lost",
                    source=status.source.value,
                    severity=AlarmSeverity.WARNING,
                    equipment=EquipmentId.SYSTEM,
                    state=EventState.ACTIVE,
                    message="OPC UA connection lost",
                    details={"connection_state": status.connection_state.value},
                )
            )
        elif not self._was_connected and connected:
            recovered = self._ever_connected
            self.store.append(
                EventCreate(
                    category=EventCategory.MONITORING,
                    event_type="monitor.recovered" if recovered else "monitor.connected",
                    source=status.source.value,
                    severity=AlarmSeverity.WARNING if recovered else None,
                    equipment=EquipmentId.SYSTEM,
                    state=EventState.RECOVERED if recovered else EventState.CHANGED,
                    message="OPC UA monitor recovered" if recovered else "OPC UA monitor connected",
                )
            )
            self._ever_connected = True

    def _observe_data_state(self, status: SystemStatus) -> None:
        if status.data_state == self._previous_data_state:
            return
        source_label = "Simulation" if status.source.value == "simulation" else "OPC UA"
        messages = {
            DataState.STALE: f"{source_label} data became stale",
            DataState.UNAVAILABLE: f"{source_label} data became unavailable",
            DataState.LIVE: f"{source_label} data returned live",
            DataState.DEGRADED: f"{source_label} data became degraded",
        }
        self.store.append(
            EventCreate(
                category=EventCategory.MONITORING,
                event_type=f"monitor.data_{status.data_state.value}",
                source=status.source.value,
                severity=AlarmSeverity.WARNING,
                equipment=EquipmentId.SYSTEM,
                state=(
                    EventState.RECOVERED
                    if status.data_state == DataState.LIVE
                    else EventState.ACTIVE
                ),
                message=messages[status.data_state],
                details={
                    "from": self._previous_data_state.value if self._previous_data_state else None,
                    "to": status.data_state.value,
                },
            )
        )
        if status.data_state in {DataState.STALE, DataState.UNAVAILABLE}:
            self._communication_gap = True
        self._previous_data_state = status.data_state

    def _observe_monitor_error(self, status: SystemStatus) -> None:
        if status.monitor_error and status.monitor_error != self._previous_error:
            self.store.append(
                EventCreate(
                    category=EventCategory.MONITORING,
                    event_type="monitor.error",
                    source=status.source.value,
                    severity=AlarmSeverity.WARNING,
                    equipment=EquipmentId.SYSTEM,
                    state=EventState.ACTIVE,
                    message=status.monitor_error,
                )
            )
        self._previous_error = status.monitor_error

    def _observe_machine_signals(self, signals: dict[str, StateSignalValue]) -> None:
        for logical_name, sample in signals.items():
            previous = self._trusted_states.get(logical_name)
            if not self._trustworthy(sample):
                if previous is not None:
                    self._gapped_signals.add(logical_name)
                continue
            current = sample.interpreted_state
            if previous is None:
                self._trusted_states[logical_name] = current
                self._gapped_signals.discard(logical_name)
                continue
            if previous != current:
                after_gap = logical_name in self._gapped_signals
                self.store.append(self._state_event(sample, previous, current, after_gap))
            self._trusted_states[logical_name] = current
            self._gapped_signals.discard(logical_name)

    @staticmethod
    def _state_event(
        sample: StateSignalValue,
        previous: InterpretedState,
        current: InterpretedState,
        after_gap: bool,
    ) -> EventCreate:
        if sample.logical_name.startswith("alarm."):
            category = EventCategory.ALARM
            event_type = (
                "alarm.activated"
                if current == InterpretedState.ACTIVE
                else "alarm.cleared"
                if current == InterpretedState.INACTIVE
                else "alarm.changed"
            )
            state = (
                EventState.ACTIVE
                if current == InterpretedState.ACTIVE
                else EventState.RECOVERED
                if current == InterpretedState.INACTIVE
                else EventState.CHANGED
            )
            severity = sample.severity
        elif sample.logical_name.startswith("interlock."):
            category = EventCategory.INTERLOCK
            event_type = "interlock.changed"
            state = (
                EventState.ACTIVE
                if current == InterpretedState.FAULT
                else EventState.RECOVERED
                if current == InterpretedState.OK
                else EventState.CHANGED
            )
            severity = sample.severity or AlarmSeverity.WARNING
        else:
            category = EventCategory.MACHINE_STATE
            event_type = "machine_state.changed"
            state = (
                EventState.ACTIVE
                if current == InterpretedState.FAULT
                else EventState.RECOVERED
                if previous == InterpretedState.FAULT
                else EventState.CHANGED
            )
            severity = sample.severity
        qualifier = " observed after communication gap" if after_gap else ""
        return EventCreate(
            category=category,
            event_type=event_type,
            source=sample.source.value,
            severity=severity,
            equipment=sample.equipment,
            state=state,
            target=sample.logical_name,
            source_timestamp=sample.source_timestamp,
            message=(
                f"{sample.display_name}: {previous.value.upper()} -> "
                f"{current.value.upper()}{qualifier}"
            ),
            details={
                "from": previous.value,
                "to": current.value,
                "observed_after_gap": after_gap,
                "change_time_known": not after_gap,
            },
        )

    def _observe_overall(self, status: SystemStatus) -> None:
        if status.data_state in {DataState.STALE, DataState.UNAVAILABLE}:
            return
        previous = self._previous_overall
        current = status.overall_state
        if previous is not None and previous != current and current != OverallState.SIMULATION:
            self.store.append(
                EventCreate(
                    category=EventCategory.MACHINE_STATE,
                    event_type="overall_state.changed",
                    source=status.source.value,
                    equipment=EquipmentId.SYSTEM,
                    state=(
                        EventState.ACTIVE
                        if current == OverallState.FAULT
                        else EventState.RECOVERED
                        if previous == OverallState.FAULT
                        else EventState.CHANGED
                    ),
                    target="overall_state",
                    message=f"Overall state: {previous.value.upper()} -> {current.value.upper()}",
                    details={
                        "from": previous.value,
                        "to": current.value,
                        "observed_after_gap": self._communication_gap,
                        "change_time_known": not self._communication_gap,
                    },
                )
            )
        self._previous_overall = current
        if status.data_state == DataState.LIVE:
            self._communication_gap = False


async def observe_monitor_events(
    settings: AppSettings,
    monitor: OPCUAMonitor | None,
    detector: EventTransitionDetector,
    stop_event: asyncio.Event,
) -> None:
    interval = min(settings.opcua.monitor_interval_seconds, 1.0) if settings.opcua else 1.0
    try:
        while not stop_event.is_set():
            try:
                detector.observe(get_system_status(settings, monitor))
            except Exception:
                logger.exception("Event transition observation failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except TimeoutError:
                pass
    except asyncio.CancelledError:
        raise
