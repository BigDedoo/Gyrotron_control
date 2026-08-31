from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from app.models import ConnectionState, SignalQuality
from app.opcua.node_map import NodeMap, NodeMapping, StateNodeMapping


class DiagnosticsEnvironment(str, Enum):
    SIMULATION = "simulation"
    LOCAL_OPCUA_TEST = "local_opcua_test"
    PRODUCTION_OPCUA = "production_opcua"


class OPCUAReadDiagnostic(BaseModel):
    """Last observation retained by the read-only client for operator diagnosis."""

    model_config = ConfigDict(extra="forbid")

    raw_value: bool | int | float | str | None = None
    converted_value: bool | int | float | None = None
    observed_datatype: str | None = None
    quality: SignalQuality = SignalQuality.UNAVAILABLE
    source_timestamp: datetime | None = None
    source_timestamp_stale: bool = False
    observed_at: datetime | None = None
    last_error: str | None = None


class OPCUASignalDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment: str
    logical_field: str
    node_id: str
    expected_datatype: str
    observed_datatype: str | None
    raw_value: bool | int | float | str | None
    converted_value: bool | int | float | None
    quality: SignalQuality
    source_timestamp: datetime | None
    backend_observed_at: datetime | None
    age_seconds: float | None
    connection_state: ConnectionState
    last_successful_read: datetime | None
    last_error: str | None
    scale: float | None
    offset: float | None
    mapping_status: Literal[
        "ready", "degraded", "stale", "bad_quality", "type_mismatch", "unavailable", "not_observed"
    ]


class OPCUADiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: DiagnosticsEnvironment
    telemetry_capability: Literal["simulated", "available_config_dependent"]
    plc_command_capability: Literal["unsupported_disabled"]
    read_only: Literal[True] = True
    connection_state: ConnectionState
    last_successful_read: datetime | None
    last_error: str | None
    signals: tuple[OPCUASignalDiagnostic, ...]


def diagnostics_environment(endpoint_url: str | None) -> DiagnosticsEnvironment:
    if endpoint_url is None:
        return DiagnosticsEnvironment.SIMULATION
    hostname = (urlsplit(endpoint_url).hostname or "").casefold()
    if hostname in {"127.0.0.1", "localhost", "::1"}:
        return DiagnosticsEnvironment.LOCAL_OPCUA_TEST
    return DiagnosticsEnvironment.PRODUCTION_OPCUA


def _equipment(logical_field: str) -> str:
    if logical_field.startswith("interlock."):
        return logical_field.split(".", 1)[1].upper()
    prefix = logical_field.split(".", 1)[0]
    return {
        "alarm": "ARC DETECTOR",
        "pulse_generator": "PULSE GENERATOR",
        "ionV": "CORE TELEMETRY",
        "ionI": "CORE TELEMETRY",
        "heatV": "CORE TELEMETRY",
        "heatI": "CORE TELEMETRY",
        "heLvl": "CORE TELEMETRY",
        "Thot": "CORE TELEMETRY",
        "Tcold": "CORE TELEMETRY",
    }.get(prefix, prefix.upper())


def _mapping_status(
    record: OPCUAReadDiagnostic | None,
) -> str:
    if record is None:
        return "not_observed"
    if record.last_error and "datatype" in record.last_error.casefold():
        return "type_mismatch"
    if record.quality == SignalQuality.BAD:
        return "bad_quality"
    if record.quality == SignalQuality.UNAVAILABLE:
        return "unavailable"
    if record.quality == SignalQuality.UNCERTAIN:
        return "degraded"
    if record.source_timestamp_stale:
        return "stale"
    return "ready"


def _signal_row(
    mapping: NodeMapping | StateNodeMapping,
    record: OPCUAReadDiagnostic | None,
    *,
    connection_state: ConnectionState,
    last_successful_read: datetime | None,
) -> OPCUASignalDiagnostic:
    now = datetime.now(timezone.utc)
    timestamp = record.source_timestamp if record is not None else None
    age = max(0.0, (now - timestamp).total_seconds()) if timestamp is not None else None
    expected = mapping.expected_type.value
    return OPCUASignalDiagnostic(
        equipment=_equipment(mapping.signal.value),
        logical_field=mapping.signal.value,
        node_id=mapping.node_id,
        expected_datatype=expected,
        observed_datatype=record.observed_datatype if record is not None else None,
        raw_value=record.raw_value if record is not None else None,
        converted_value=record.converted_value if record is not None else None,
        quality=record.quality if record is not None else SignalQuality.UNAVAILABLE,
        source_timestamp=timestamp,
        backend_observed_at=record.observed_at if record is not None else None,
        age_seconds=round(age, 3) if age is not None else None,
        connection_state=connection_state,
        last_successful_read=last_successful_read,
        last_error=record.last_error if record is not None else "Signal has not been observed yet",
        scale=mapping.scale if isinstance(mapping, NodeMapping) else None,
        offset=mapping.offset if isinstance(mapping, NodeMapping) else None,
        mapping_status=_mapping_status(record),
    )


def build_diagnostics(
    *,
    endpoint_url: str | None,
    node_map: NodeMap | None,
    observations: dict[str, OPCUAReadDiagnostic] | None,
    connection_state: ConnectionState,
    last_successful_read: datetime | None,
    last_error: str | None,
) -> OPCUADiagnosticsResponse:
    if node_map is None:
        environment = diagnostics_environment(endpoint_url)
        return OPCUADiagnosticsResponse(
            environment=environment,
            telemetry_capability=(
                "simulated"
                if environment == DiagnosticsEnvironment.SIMULATION
                else "available_config_dependent"
            ),
            plc_command_capability="unsupported_disabled",
            connection_state=connection_state,
            last_successful_read=last_successful_read,
            last_error=last_error,
            signals=(),
        )
    records = observations or {}
    mappings = (*node_map.signals, *node_map.state_signals)
    return OPCUADiagnosticsResponse(
        environment=diagnostics_environment(endpoint_url),
        telemetry_capability="available_config_dependent",
        plc_command_capability="unsupported_disabled",
        connection_state=connection_state,
        last_successful_read=last_successful_read,
        last_error=last_error,
        signals=tuple(
            _signal_row(
                mapping,
                records.get(mapping.signal.value),
                connection_state=connection_state,
                last_successful_read=last_successful_read,
            )
            for mapping in mappings
        ),
    )
