import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import OPCUASettings
from app.models import ConnectionState, DataSource, DataState, SignalQuality, TelemetryPoint
from app.opcua.client import OPCUAClientError, ReadOnlyOPCUAClient
from app.opcua.node_map import LogicalSignal, NodeMap


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitorView:
    connection_state: ConnectionState
    data_state: DataState
    last_connection_attempt: datetime | None
    last_successful_read: datetime | None
    snapshot: TelemetryPoint | None
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
        self._snapshot: TelemetryPoint | None = None
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

    def _data_state(self) -> DataState:
        snapshot = self._snapshot
        if snapshot is None or self._last_successful_read is None:
            return DataState.UNAVAILABLE
        age = (datetime.now(timezone.utc) - self._last_successful_read).total_seconds()
        if age > self.settings.stale_after_seconds:
            return DataState.UNAVAILABLE
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
        qualities = [getattr(snapshot, signal.value).quality for signal in LogicalSignal]
        if all(quality == SignalQuality.GOOD for quality in qualities):
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
        usable = [
            sample
            for sample in values.values()
            if sample.value is not None
            and sample.quality in {SignalQuality.GOOD, SignalQuality.UNCERTAIN}
        ]
        if not usable:
            raise OPCUAClientError("No configured telemetry signal is usable")

        self._sequence += 1
        now = datetime.now(timezone.utc)
        self._snapshot = TelemetryPoint(
            timestamp=now,
            source=DataSource.OPCUA,
            sequence=self._sequence,
            **{signal.value: values[signal] for signal in LogicalSignal},
        )
        self._last_successful_read = now
        self._connection_state = ConnectionState.CONNECTED
        self._error = (
            None
            if all(sample.quality == SignalQuality.GOOD for sample in values.values())
            else "One or more OPC UA telemetry signals are degraded"
        )

    async def _wait(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
        except TimeoutError:
            pass
