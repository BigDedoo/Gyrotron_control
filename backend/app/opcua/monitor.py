import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import OPCUASettings
from app.equipment import build_equipment_snapshot
from app.models import (
    ConnectionState,
    DataSource,
    DataState,
    InterpretedState,
    MachineStatePoint,
    MappingCoverage,
    OPCUASnapshot,
    SignalQuality,
    TelemetryPoint,
)
from app.opcua.client import OPCUAClientError, ReadOnlyOPCUAClient
from app.opcua.diagnostics import OPCUADiagnosticsResponse, build_diagnostics
from app.opcua.node_map import (
    REQUIRED_SIGNALS,
    LogicalStateSignal,
    NodeMap,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorView:
    connection_state: ConnectionState
    data_state: DataState
    last_connection_attempt: datetime | None
    last_successful_read: datetime | None
    snapshot: OPCUASnapshot | None
    error: str | None


class OPCUAMonitor:
    def __init__(
        self,
        settings: OPCUASettings,
        node_map: NodeMap,
        *,
        client: ReadOnlyOPCUAClient | None = None,
    ) -> None:
        self.settings = settings
        self.node_map = node_map
        self.client = client or ReadOnlyOPCUAClient(settings)
        self._connection_state = ConnectionState.DISCONNECTED
        self._last_connection_attempt: datetime | None = None
        self._last_successful_read: datetime | None = None
        self._snapshot: OPCUASnapshot | None = None
        self._error: str | None = None
        self._sequence = 0
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="opcua-readonly-monitor")

    async def stop(self) -> None:
        self._stop_event.set()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.client.disconnect()
        self._connection_state = ConnectionState.DISCONNECTED

    def view(self) -> MonitorView:
        data_state = self._data_state()
        return MonitorView(
            connection_state=self._connection_state,
            data_state=data_state,
            last_connection_attempt=self._last_connection_attempt,
            last_successful_read=self._last_successful_read,
            snapshot=self._snapshot,
            error=self._error,
        )

    def diagnostics(self) -> OPCUADiagnosticsResponse:
        return build_diagnostics(
            endpoint_url=self.settings.endpoint_url,
            node_map=self.node_map,
            observations=self.client.diagnostics_snapshot(),
            connection_state=self._connection_state,
            last_successful_read=self._last_successful_read,
            last_error=self._error,
        )

    def _data_state(self) -> DataState:
        snapshot = self._snapshot
        if snapshot is None or self._last_successful_read is None:
            return DataState.UNAVAILABLE
        age = (datetime.now(timezone.utc) - self._last_successful_read).total_seconds()
        if age > self.settings.stale_after_seconds:
            return DataState.UNAVAILABLE
        stale_source_observed = any(
            sample.source_timestamp_stale
            for sample in self.client.diagnostics_snapshot().values()
            if sample.quality in {SignalQuality.GOOD, SignalQuality.UNCERTAIN}
        )
        if stale_source_observed:
            return DataState.STALE
        snapshot_predates_connection = (
            self._last_connection_attempt is not None
            and self._last_successful_read < self._last_connection_attempt
        )
        if (
            self._connection_state != ConnectionState.CONNECTED
            or snapshot_predates_connection
            or age > self.settings.monitor_interval_seconds * 2
        ):
            return DataState.STALE
        qualities = [
            getattr(snapshot.telemetry, signal.value).quality for signal in REQUIRED_SIGNALS
        ]
        qualities.extend(sample.quality for sample in snapshot.machine_state.signals.values())
        state_interpretations_valid = all(
            sample.interpreted_state != InterpretedState.UNKNOWN
            for sample in snapshot.machine_state.signals.values()
        )
        if all(quality == SignalQuality.GOOD for quality in qualities) and state_interpretations_valid:
            return DataState.LIVE
        return DataState.DEGRADED

    async def _run(self) -> None:
        reconnect_delay = self.settings.reconnect_initial_seconds
        try:
            while not self._stop_event.is_set():
                if not self.client.connected:
                    self._connection_state = ConnectionState.CONNECTING
                    self._last_connection_attempt = datetime.now(timezone.utc)
                    try:
                        await self.client.connect()
                    except OPCUAClientError:
                        self._connection_state = ConnectionState.ERROR
                        self._error = "OPC UA connection failed"
                        await self._wait(reconnect_delay)
                        reconnect_delay = min(
                            reconnect_delay * 2,
                            self.settings.reconnect_max_seconds,
                        )
                        continue
                    self._connection_state = ConnectionState.CONNECTED
                    self._error = None
                    reconnect_delay = self.settings.reconnect_initial_seconds

                try:
                    await self._read_once()
                except OPCUAClientError:
                    logger.warning("Read-only OPC UA monitoring cycle failed")
                    self._error = "OPC UA telemetry read failed"
                    await self.client.disconnect()
                    self._connection_state = ConnectionState.DISCONNECTED
                    await self._wait(reconnect_delay)
                    reconnect_delay = min(
                        reconnect_delay * 2,
                        self.settings.reconnect_max_seconds,
                    )
                    continue

                await self._wait(self.settings.monitor_interval_seconds)
        except asyncio.CancelledError:
            raise
        finally:
            await self.client.disconnect()
            self._connection_state = ConnectionState.DISCONNECTED

    async def _read_once(self) -> None:
        values = await self.client.read_signals(self.node_map.signals)
        state_values = await self.client.read_state_signals(self.node_map.state_signals)
        usable = [
            values[signal]
            for signal in REQUIRED_SIGNALS
            if (
                values[signal].value is not None
                and values[signal].quality in {SignalQuality.GOOD, SignalQuality.UNCERTAIN}
            )
        ]
        if not usable:
            raise OPCUAClientError("No configured telemetry signal is usable")

        self._sequence += 1
        now = datetime.now(timezone.utc)
        telemetry = TelemetryPoint(
            timestamp=now,
            source=DataSource.OPCUA,
            sequence=self._sequence,
            **{signal.value: values[signal] for signal in REQUIRED_SIGNALS},
        )
        mapped = set(state_values)
        trustworthy = sum(
            sample.quality == SignalQuality.GOOD
            and sample.interpreted_state != InterpretedState.UNKNOWN
            for sample in state_values.values()
        )
        coverage = MappingCoverage(
            total=len(LogicalStateSignal),
            mapped=len(mapped),
            trustworthy=trustworthy,
            complete=(
                len(mapped) == len(LogicalStateSignal)
                and trustworthy == len(LogicalStateSignal)
            ),
            missing=[signal.value for signal in LogicalStateSignal if signal not in mapped],
            unavailable=[
                signal.value
                for signal, sample in state_values.items()
                if sample.quality != SignalQuality.GOOD
                or sample.interpreted_state == InterpretedState.UNKNOWN
            ],
        )
        machine_state = MachineStatePoint(
            timestamp=now,
            source=DataSource.OPCUA,
            sequence=self._sequence,
            signals={signal.value: sample for signal, sample in state_values.items()},
            coverage=coverage,
        )
        self._snapshot = OPCUASnapshot(
            timestamp=now,
            sequence=self._sequence,
            telemetry=telemetry,
            machine_state=machine_state,
            equipment=build_equipment_snapshot(
                source=DataSource.OPCUA,
                timestamp=now,
                sequence=self._sequence,
                data_state=DataState.LIVE,
                readings=values,
                state_signals=state_values,
            ),
        )
        self._last_successful_read = now
        self._connection_state = ConnectionState.CONNECTED
        self._error = (
            None
            if all(sample.quality == SignalQuality.GOOD for sample in values.values())
            and all(
                sample.quality == SignalQuality.GOOD
                and sample.interpreted_state != InterpretedState.UNKNOWN
                for sample in state_values.values()
            )
            else "One or more configured OPC UA signals are degraded"
        )

    async def _wait(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass
