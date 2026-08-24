import asyncio
import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from asyncua import Client

from app.core.config import OPCUASettings
from app.models import (
    ConnectionState,
    DataSource,
    DataState,
    InterpretedState,
    SignalQuality,
    SignalValue,
    StateSignalValue,
)
from app.opcua.node_map import (
    ExpectedType,
    LogicalSignal,
    LogicalStateSignal,
    NodeMapping,
    StateExpectedType,
    StateNodeMapping,
)


logger = logging.getLogger(__name__)


class OPCUAClientError(RuntimeError):
    pass


class OPCUAConnectionError(OPCUAClientError):
    pass


class OPCUAReadError(OPCUAClientError):
    pass


def _source_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _quality(status_code: Any) -> SignalQuality:
    if status_code is None:
        return SignalQuality.UNAVAILABLE
    if status_code.is_good():
        return SignalQuality.GOOD
    if status_code.is_uncertain():
        return SignalQuality.UNCERTAIN
    return SignalQuality.BAD


def _normalize_value(raw: Any, mapping: NodeMapping) -> float:
    if isinstance(raw, bool):
        raise TypeError("boolean is not a numeric telemetry value")
    if mapping.expected_type == ExpectedType.INTEGER:
        if not isinstance(raw, int):
            raise TypeError("OPC UA value is not the configured integer type")
    elif not isinstance(raw, float):
        raise TypeError("OPC UA value is not the configured floating-point type")
    return float(raw) * mapping.scale + mapping.offset


def _normalize_state_value(raw: Any, mapping: StateNodeMapping) -> bool | int:
    if mapping.expected_type == StateExpectedType.BOOLEAN:
        if not isinstance(raw, bool):
            raise TypeError("OPC UA value is not the configured boolean type")
        return raw
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError("OPC UA value is not the configured integer type")
    return raw


def _unavailable_state(mapping: StateNodeMapping, observed_at: datetime) -> StateSignalValue:
    return StateSignalValue(
        logical_name=mapping.signal.value,
        display_name=mapping.label,
        group=mapping.display_group,
        mapped=True,
        raw_value=None,
        interpreted_state=InterpretedState.UNKNOWN,
        quality=SignalQuality.UNAVAILABLE,
        source_timestamp=None,
        observed_at=observed_at,
        source=DataSource.OPCUA,
        data_state=DataState.UNAVAILABLE,
        severity=mapping.alarm_severity,
    )


class ReadOnlyOPCUAClient:
    """A deliberately read-only OPC UA boundary.

    This class exposes connection lifecycle and typed reads only. Hardware write helpers
    are intentionally absent.
    """

    def __init__(
        self,
        settings: OPCUASettings,
        *,
        client_factory: Callable[[str, float], Client] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or (lambda url, timeout: Client(url, timeout=timeout))
        self._client: Client | None = None
        self.connection_state = ConnectionState.DISCONNECTED
        self._lifecycle_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self.connection_state == ConnectionState.CONNECTED and self._client is not None

    async def connect(self) -> None:
        async with self._lifecycle_lock:
            if self.connected:
                return
            await self._disconnect_unlocked()
            self.connection_state = ConnectionState.CONNECTING
            endpoint = urlsplit(self.settings.endpoint_url)
            logger.info("Connecting read-only OPC UA monitor to %s:%s", endpoint.hostname, endpoint.port)
            client = self._client_factory(
                self.settings.endpoint_url,
                self.settings.read_timeout_seconds,
            )
            try:
                if self.settings.security_policy != "None":
                    certificate = str(self.settings.client_certificate_path)
                    private_key = str(self.settings.client_private_key_path)
                    if self.settings.client_private_key_password is not None:
                        private_key += "::" + self.settings.client_private_key_password.get_secret_value()
                    security = ",".join(
                        [
                            self.settings.security_policy,
                            self.settings.security_mode,
                            certificate,
                            private_key,
                        ]
                    )
                    if self.settings.server_certificate_path is not None:
                        security += "," + str(self.settings.server_certificate_path)
                    await client.set_security_string(security)
                if self.settings.username is not None and self.settings.password is not None:
                    client.set_user(self.settings.username)
                    client.set_password(self.settings.password.get_secret_value())
                await asyncio.wait_for(
                    client.connect(),
                    timeout=self.settings.connect_timeout_seconds,
                )
            except Exception as exc:
                self.connection_state = ConnectionState.ERROR
                try:
                    await asyncio.wait_for(
                        client.disconnect(),
                        timeout=self.settings.connect_timeout_seconds,
                    )
                except Exception:
                    pass
                logger.warning("Read-only OPC UA connection attempt failed (%s)", type(exc).__name__)
                raise OPCUAConnectionError("OPC UA connection failed") from exc
            self._client = client
            self.connection_state = ConnectionState.CONNECTED
            logger.info("Read-only OPC UA monitor connected")

    async def disconnect(self) -> None:
        async with self._lifecycle_lock:
            await self._disconnect_unlocked()

    async def _disconnect_unlocked(self) -> None:
        client, self._client = self._client, None
        self.connection_state = ConnectionState.DISCONNECTED
        if client is None:
            return
        try:
            await asyncio.wait_for(
                client.disconnect(),
                timeout=self.settings.connect_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("Read-only OPC UA disconnect was incomplete (%s)", type(exc).__name__)
        else:
            logger.info("Read-only OPC UA monitor disconnected")

    async def read_signal(self, mapping: NodeMapping) -> SignalValue:
        client = self._client
        if not self.connected or client is None:
            raise OPCUAReadError("OPC UA client is not connected")
        try:
            node = client.get_node(mapping.node_id)
            data_value = await asyncio.wait_for(
                node.read_data_value(raise_on_bad_status=False),
                timeout=self.settings.read_timeout_seconds,
            )
        except Exception as exc:
            raise OPCUAReadError("OPC UA signal read failed") from exc

        quality = _quality(data_value.StatusCode)
        timestamp = _source_timestamp(data_value.SourceTimestamp)
        if quality in {SignalQuality.BAD, SignalQuality.UNAVAILABLE}:
            return SignalValue(
                value=None,
                unit=mapping.unit,
                quality=quality,
                source_timestamp=timestamp,
            )

        raw = data_value.Value.Value if data_value.Value is not None else None
        try:
            value = _normalize_value(raw, mapping)
        except (TypeError, ValueError, OverflowError):
            return SignalValue(
                value=None,
                unit=mapping.unit,
                quality=SignalQuality.BAD,
                source_timestamp=timestamp,
            )
        return SignalValue(
            value=value,
            unit=mapping.unit,
            quality=quality,
            source_timestamp=timestamp,
        )

    async def read_signals(
        self,
        mappings: Iterable[NodeMapping],
    ) -> dict[LogicalSignal, SignalValue]:
        ordered = tuple(mappings)
        results = await asyncio.gather(
            *(self.read_signal(mapping) for mapping in ordered),
            return_exceptions=True,
        )
        if results and all(isinstance(result, Exception) for result in results):
            raise OPCUAReadError("All configured OPC UA signal reads failed")

        values: dict[LogicalSignal, SignalValue] = {}
        for mapping, result in zip(ordered, results, strict=True):
            if isinstance(result, Exception):
                values[mapping.signal] = SignalValue(
                    value=None,
                    unit=mapping.unit,
                    quality=SignalQuality.UNAVAILABLE,
                    source_timestamp=None,
                )
            else:
                values[mapping.signal] = result
        return values

    async def read_state_signal(self, mapping: StateNodeMapping) -> StateSignalValue:
        client = self._client
        if not self.connected or client is None:
            raise OPCUAReadError("OPC UA client is not connected")
        observed_at = datetime.now(timezone.utc)
        try:
            node = client.get_node(mapping.node_id)
            data_value = await asyncio.wait_for(
                node.read_data_value(raise_on_bad_status=False),
                timeout=self.settings.read_timeout_seconds,
            )
            observed_at = datetime.now(timezone.utc)
        except Exception as exc:
            raise OPCUAReadError("OPC UA state signal read failed") from exc

        quality = _quality(data_value.StatusCode)
        timestamp = _source_timestamp(data_value.SourceTimestamp)
        if quality in {SignalQuality.BAD, SignalQuality.UNAVAILABLE}:
            return _unavailable_state(mapping, observed_at).model_copy(
                update={"quality": quality, "source_timestamp": timestamp}
            )

        raw = data_value.Value.Value if data_value.Value is not None else None
        try:
            normalized = _normalize_state_value(raw, mapping)
        except (TypeError, ValueError, OverflowError):
            return _unavailable_state(mapping, observed_at).model_copy(
                update={
                    "quality": SignalQuality.BAD,
                    "source_timestamp": timestamp,
                    "data_state": DataState.DEGRADED,
                }
            )

        interpreted = (
            mapping.interpret(normalized)
            if quality == SignalQuality.GOOD
            else InterpretedState.UNKNOWN
        )
        return StateSignalValue(
            logical_name=mapping.signal.value,
            display_name=mapping.label,
            group=mapping.display_group,
            mapped=True,
            raw_value=normalized,
            interpreted_state=interpreted,
            quality=quality,
            source_timestamp=timestamp,
            observed_at=observed_at,
            source=DataSource.OPCUA,
            data_state=(
                DataState.LIVE
                if quality == SignalQuality.GOOD and interpreted != InterpretedState.UNKNOWN
                else DataState.DEGRADED
            ),
            severity=mapping.alarm_severity,
        )

    async def read_state_signals(
        self,
        mappings: Iterable[StateNodeMapping],
    ) -> dict[LogicalStateSignal, StateSignalValue]:
        ordered = tuple(mappings)
        results = await asyncio.gather(
            *(self.read_state_signal(mapping) for mapping in ordered),
            return_exceptions=True,
        )
        observed_at = datetime.now(timezone.utc)
        values: dict[LogicalStateSignal, StateSignalValue] = {}
        for mapping, result in zip(ordered, results, strict=True):
            values[mapping.signal] = (
                _unavailable_state(mapping, observed_at)
                if isinstance(result, Exception)
                else result
            )
        return values
