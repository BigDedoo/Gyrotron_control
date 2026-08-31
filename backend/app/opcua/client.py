import asyncio
import logging
import math
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from asyncua import Client, ua
from asyncua.crypto import security_policies

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
from app.opcua.diagnostics import OPCUAReadDiagnostic


logger = logging.getLogger(__name__)


SECURITY_POLICIES = {
    "Basic256Sha256": security_policies.SecurityPolicyBasic256Sha256,
    "Aes128Sha256RsaOaep": security_policies.SecurityPolicyAes128Sha256RsaOaep,
    "Aes256Sha256RsaPss": security_policies.SecurityPolicyAes256Sha256RsaPss,
}


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
    if getattr(status_code, "value", None) == ua.StatusCodes.BadNodeIdUnknown:
        return SignalQuality.UNAVAILABLE
    if status_code.is_good():
        return SignalQuality.GOOD
    if status_code.is_uncertain():
        return SignalQuality.UNCERTAIN
    return SignalQuality.BAD


def _observed_datatype(data_value: Any) -> str | None:
    variant = getattr(data_value, "Value", None)
    variant_type = getattr(variant, "VariantType", None)
    return getattr(variant_type, "name", None) or (
        type(getattr(variant, "Value", None)).__name__ if variant is not None else None
    )


def _diagnostic_raw(raw: Any) -> Any:
    if isinstance(raw, float) and not math.isfinite(raw):
        if math.isnan(raw):
            return "NaN"
        return "+Inf" if raw > 0 else "-Inf"
    return raw


def _normalize_value(raw: Any, mapping: NodeMapping) -> float:
    if isinstance(raw, bool):
        raise TypeError("boolean is not a numeric telemetry value")
    if mapping.expected_type == ExpectedType.INTEGER:
        if not isinstance(raw, int):
            raise TypeError("OPC UA value is not the configured integer type")
    elif not isinstance(raw, float):
        raise TypeError("OPC UA value is not the configured floating-point type")
    numeric = float(raw)
    if not math.isfinite(numeric):
        raise ValueError("OPC UA numeric value is not finite")
    normalized = numeric * mapping.scale + mapping.offset
    if not math.isfinite(normalized):
        raise ValueError("normalized OPC UA numeric value is not finite")
    return normalized


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
        self._diagnostics: dict[str, OPCUAReadDiagnostic] = {}
        self._source_timestamp_seen_fresh: dict[str, bool] = {}

    @property
    def connected(self) -> bool:
        return self.connection_state == ConnectionState.CONNECTED and self._client is not None

    def diagnostics_snapshot(self) -> dict[str, OPCUAReadDiagnostic]:
        return {
            name: diagnostic.model_copy(deep=True)
            for name, diagnostic in self._diagnostics.items()
        }

    def _source_timestamp_stale(
        self,
        logical_name: str,
        source_timestamp: datetime | None,
        observed_at: datetime,
    ) -> bool:
        if source_timestamp is None:
            return False
        age = max(0.0, (observed_at - source_timestamp).total_seconds())
        if age <= self.settings.stale_after_seconds:
            self._source_timestamp_seen_fresh[logical_name] = True
            return False
        return not self._source_timestamp_seen_fresh.get(logical_name, False)

    def _record_unavailable(
        self,
        logical_name: str,
        error: str,
        observed_at: datetime | None = None,
    ) -> None:
        previous = self._diagnostics.get(logical_name)
        if previous is None:
            self._diagnostics[logical_name] = OPCUAReadDiagnostic(
                observed_at=observed_at,
                last_error=error,
            )
            return
        self._diagnostics[logical_name] = previous.model_copy(
            update={"quality": SignalQuality.UNAVAILABLE, "last_error": error}
        )

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
                    await client.set_security(
                        SECURITY_POLICIES[self.settings.security_policy],
                        self.settings.client_certificate_path,
                        self.settings.client_private_key_path,
                        private_key_password=(
                            self.settings.client_private_key_password.get_secret_value()
                            if self.settings.client_private_key_password is not None
                            else None
                        ),
                        server_certificate=self.settings.server_certificate_path,
                        mode=ua.MessageSecurityMode.SignAndEncrypt,
                    )
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
        observed_at = datetime.now(timezone.utc)
        try:
            node = client.get_node(mapping.node_id)
            data_value = await asyncio.wait_for(
                node.read_data_value(raise_on_bad_status=False),
                timeout=self.settings.read_timeout_seconds,
            )
            observed_at = datetime.now(timezone.utc)
        except Exception as exc:
            self._record_unavailable(
                mapping.signal.value,
                f"Signal read failed: {type(exc).__name__}",
                observed_at,
            )
            raise OPCUAReadError("OPC UA signal read failed") from exc

        quality = _quality(data_value.StatusCode)
        timestamp = _source_timestamp(data_value.SourceTimestamp)
        raw = data_value.Value.Value if data_value.Value is not None else None
        observed_datatype = _observed_datatype(data_value)
        if quality in {SignalQuality.BAD, SignalQuality.UNAVAILABLE}:
            self._diagnostics[mapping.signal.value] = OPCUAReadDiagnostic(
                raw_value=_diagnostic_raw(raw),
                observed_datatype=observed_datatype,
                quality=quality,
                source_timestamp=timestamp,
                source_timestamp_stale=self._source_timestamp_stale(
                    mapping.signal.value, timestamp, observed_at
                ),
                observed_at=observed_at,
                last_error=f"OPC UA quality is {quality.value}",
            )
            return SignalValue(
                value=None,
                unit=mapping.unit,
                quality=quality,
                source_timestamp=timestamp,
                observed_at=observed_at,
            )
        try:
            value = _normalize_value(raw, mapping)
        except (TypeError, ValueError, OverflowError) as exc:
            self._diagnostics[mapping.signal.value] = OPCUAReadDiagnostic(
                raw_value=_diagnostic_raw(raw),
                observed_datatype=observed_datatype,
                quality=SignalQuality.BAD,
                source_timestamp=timestamp,
                source_timestamp_stale=self._source_timestamp_stale(
                    mapping.signal.value, timestamp, observed_at
                ),
                observed_at=observed_at,
                last_error=f"Datatype/value validation failed: {exc}",
            )
            return SignalValue(
                value=None,
                unit=mapping.unit,
                quality=SignalQuality.BAD,
                source_timestamp=timestamp,
                observed_at=observed_at,
            )
        self._diagnostics[mapping.signal.value] = OPCUAReadDiagnostic(
            raw_value=_diagnostic_raw(raw),
            converted_value=value,
            observed_datatype=observed_datatype,
            quality=quality,
            source_timestamp=timestamp,
            source_timestamp_stale=self._source_timestamp_stale(
                mapping.signal.value, timestamp, observed_at
            ),
            observed_at=observed_at,
            last_error=None,
        )
        return SignalValue(
            value=value,
            unit=mapping.unit,
            quality=quality,
            source_timestamp=timestamp,
            observed_at=observed_at,
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
                self._record_unavailable(
                    mapping.signal.value,
                    f"Signal unavailable: {type(result).__name__}",
                )
                values[mapping.signal] = SignalValue(
                    value=None,
                    unit=mapping.unit,
                    quality=SignalQuality.UNAVAILABLE,
                    source_timestamp=None,
                    observed_at=None,
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
            self._record_unavailable(
                mapping.signal.value,
                f"State signal read failed: {type(exc).__name__}",
                observed_at,
            )
            raise OPCUAReadError("OPC UA state signal read failed") from exc

        quality = _quality(data_value.StatusCode)
        timestamp = _source_timestamp(data_value.SourceTimestamp)
        raw = data_value.Value.Value if data_value.Value is not None else None
        observed_datatype = _observed_datatype(data_value)
        if quality in {SignalQuality.BAD, SignalQuality.UNAVAILABLE}:
            self._diagnostics[mapping.signal.value] = OPCUAReadDiagnostic(
                raw_value=_diagnostic_raw(raw),
                observed_datatype=observed_datatype,
                quality=quality,
                source_timestamp=timestamp,
                source_timestamp_stale=self._source_timestamp_stale(
                    mapping.signal.value, timestamp, observed_at
                ),
                observed_at=observed_at,
                last_error=f"OPC UA quality is {quality.value}",
            )
            return _unavailable_state(mapping, observed_at).model_copy(
                update={"quality": quality, "source_timestamp": timestamp}
            )
        try:
            normalized = _normalize_state_value(raw, mapping)
        except (TypeError, ValueError, OverflowError) as exc:
            self._diagnostics[mapping.signal.value] = OPCUAReadDiagnostic(
                raw_value=_diagnostic_raw(raw),
                observed_datatype=observed_datatype,
                quality=SignalQuality.BAD,
                source_timestamp=timestamp,
                source_timestamp_stale=self._source_timestamp_stale(
                    mapping.signal.value, timestamp, observed_at
                ),
                observed_at=observed_at,
                last_error=f"Datatype/value validation failed: {exc}",
            )
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
        self._diagnostics[mapping.signal.value] = OPCUAReadDiagnostic(
            raw_value=_diagnostic_raw(raw),
            converted_value=normalized,
            observed_datatype=observed_datatype,
            quality=quality,
            source_timestamp=timestamp,
            source_timestamp_stale=self._source_timestamp_stale(
                mapping.signal.value, timestamp, observed_at
            ),
            observed_at=observed_at,
            last_error=None,
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
            if isinstance(result, Exception):
                self._record_unavailable(
                    mapping.signal.value,
                    f"State signal unavailable: {type(result).__name__}",
                    observed_at,
                )
            values[mapping.signal] = (
                _unavailable_state(mapping, observed_at)
                if isinstance(result, Exception)
                else result
            )
        return values
