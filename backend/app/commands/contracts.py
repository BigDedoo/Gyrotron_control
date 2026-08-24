from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LogicalCommand(str, Enum):
    APPLY_SETPOINT = "setpoint.apply"
    CPS_RECTIFIER_SET = "cps.rectifier.set"
    CPS_CONVERTER_SET = "cps.converter.set"
    APS_RECTIFIER_SET = "aps.rectifier.set"
    APS_CONVERTER_SET = "aps.converter.set"
    PROTECTION_RESET = "protection.reset"
    INTERLOCK_RESET = "interlock.reset"
    EMERGENCY_SHUTDOWN = "emergency.shutdown"


class RequestedValueType(str, Enum):
    NUMBER = "number"
    BOOLEAN = "boolean"
    NONE = "none"


class CommandContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command: LogicalCommand
    target: str = Field(min_length=1, max_length=128)
    requested_value_type: RequestedValueType
    engineering_unit: str | None = Field(default=None, max_length=32)
    authorization_policy: str | None = Field(default=None, max_length=256)
    confirmation_policy: str | None = Field(default=None, max_length=256)
    controls_engineering_approval: str | None = Field(default=None, max_length=256)
    allowed_min: float | None = None
    allowed_max: float | None = None
    allowed_values: tuple[str, ...] | None = None
    scaling_semantics: str | None = Field(default=None, max_length=512)
    command_polarity: str | None = Field(default=None, max_length=256)
    pulse_or_hold_semantics: str | None = Field(default=None, max_length=256)
    required_machine_preconditions: tuple[str, ...] | None = None
    plc_write_node_id: str | None = Field(default=None, max_length=512)
    plc_write_type: str | None = Field(default=None, max_length=128)
    readback_node_id: str | None = Field(default=None, max_length=512)
    readback_semantics: str | None = Field(default=None, max_length=512)
    readback_tolerance: float | None = Field(default=None, ge=0)
    settling_semantics: str | None = Field(default=None, max_length=512)
    acknowledgement_node_id: str | None = Field(default=None, max_length=512)
    acknowledgement_semantics: str | None = Field(default=None, max_length=512)
    execution_timeout_seconds: float | None = Field(default=None, gt=0)
    acknowledgement_timeout_seconds: float | None = Field(default=None, gt=0)
    failure_semantics: str | None = Field(default=None, max_length=512)
    network_loss_semantics: str | None = Field(default=None, max_length=512)
    retry_policy: str | None = Field(default=None, max_length=512)
    idempotency_semantics: str | None = Field(default=None, max_length=512)
    software_emergency_shutdown_approved: bool | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "CommandContract":
        if (
            self.allowed_min is not None
            and self.allowed_max is not None
            and self.allowed_max <= self.allowed_min
        ):
            raise ValueError("allowed_max must be greater than allowed_min")
        return self


class CommandContractTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    purpose: Literal["template"]
    commands: tuple[CommandContract, ...]


def phase4_command_contracts() -> tuple[CommandContract, ...]:
    definitions = (
        (LogicalCommand.APPLY_SETPOINT, "setpoints", RequestedValueType.NUMBER),
        (LogicalCommand.CPS_RECTIFIER_SET, "CPS rectifier", RequestedValueType.BOOLEAN),
        (LogicalCommand.CPS_CONVERTER_SET, "CPS converter", RequestedValueType.BOOLEAN),
        (LogicalCommand.APS_RECTIFIER_SET, "APS rectifier", RequestedValueType.BOOLEAN),
        (LogicalCommand.APS_CONVERTER_SET, "APS converter", RequestedValueType.BOOLEAN),
        (LogicalCommand.PROTECTION_RESET, "protection", RequestedValueType.NONE),
        (LogicalCommand.INTERLOCK_RESET, "interlocks", RequestedValueType.NONE),
        (LogicalCommand.EMERGENCY_SHUTDOWN, "emergency shutdown", RequestedValueType.NONE),
    )
    return tuple(
        CommandContract(command=command, target=target, requested_value_type=value_type)
        for command, target, value_type in definitions
    )
