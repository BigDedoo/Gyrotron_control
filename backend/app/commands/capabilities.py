from enum import Enum
from typing import Literal

from pydantic import BaseModel

from app.commands.contracts import (
    CommandContract,
    LogicalCommand,
    RequestedValueType,
    phase4_command_contracts,
)


class CommandBlocker(str, Enum):
    EXECUTION_NOT_IMPLEMENTED = "execution_not_implemented"
    AUDIT_FAIL_CLOSED_NOT_IMPLEMENTED = "audit_fail_closed_not_implemented"
    WRITE_NODE_UNRESOLVED = "write_node_unresolved"
    WRITE_TYPE_UNRESOLVED = "write_type_unresolved"
    READBACK_UNRESOLVED = "readback_unresolved"
    ACKNOWLEDGEMENT_UNRESOLVED = "acknowledgement_unresolved"
    PRECONDITIONS_UNRESOLVED = "preconditions_unresolved"
    AUTHORIZATION_UNAPPROVED = "authorization_unapproved"
    CONFIRMATION_UNAPPROVED = "confirmation_unapproved"
    CONTROLS_APPROVAL_UNRESOLVED = "controls_approval_unresolved"
    TIMEOUT_UNRESOLVED = "timeout_unresolved"
    FAILURE_BEHAVIOR_UNRESOLVED = "failure_behavior_unresolved"
    NETWORK_LOSS_UNRESOLVED = "network_loss_unresolved"
    RETRY_IDEMPOTENCY_UNRESOLVED = "retry_idempotency_unresolved"
    RANGE_SCALING_UNRESOLVED = "range_scaling_unresolved"
    POLARITY_UNRESOLVED = "polarity_unresolved"
    PULSE_HOLD_UNRESOLVED = "pulse_hold_unresolved"
    EMERGENCY_APPROPRIATENESS_UNRESOLVED = "emergency_appropriateness_unresolved"


BLOCKER_MESSAGES: dict[CommandBlocker, str] = {
    CommandBlocker.EXECUTION_NOT_IMPLEMENTED: "No PLC command execution capability exists",
    CommandBlocker.AUDIT_FAIL_CLOSED_NOT_IMPLEMENTED: "Mandatory fail-closed command audit is not commissioned",
    CommandBlocker.WRITE_NODE_UNRESOLVED: "PLC write NodeId is unresolved",
    CommandBlocker.WRITE_TYPE_UNRESOLVED: "PLC write type is unresolved",
    CommandBlocker.READBACK_UNRESOLVED: "Readback NodeId and semantics are unresolved",
    CommandBlocker.ACKNOWLEDGEMENT_UNRESOLVED: "Acknowledgement/completion semantics are unresolved",
    CommandBlocker.PRECONDITIONS_UNRESOLVED: "Required machine-state preconditions are unresolved",
    CommandBlocker.AUTHORIZATION_UNAPPROVED: "Authorization policy is unapproved",
    CommandBlocker.CONFIRMATION_UNAPPROVED: "Operator confirmation policy is unapproved",
    CommandBlocker.CONTROLS_APPROVAL_UNRESOLVED: "Controls/safety engineering approval is unresolved",
    CommandBlocker.TIMEOUT_UNRESOLVED: "Execution and acknowledgement timeout behavior is unresolved",
    CommandBlocker.FAILURE_BEHAVIOR_UNRESOLVED: "Failure behavior is unresolved",
    CommandBlocker.NETWORK_LOSS_UNRESOLVED: "Network-loss behavior is unresolved",
    CommandBlocker.RETRY_IDEMPOTENCY_UNRESOLVED: "Retry and idempotency semantics are unresolved",
    CommandBlocker.RANGE_SCALING_UNRESOLVED: "Approved engineering unit, range, scaling, tolerance, and settling semantics are unresolved",
    CommandBlocker.POLARITY_UNRESOLVED: "Command polarity and allowed values are unresolved",
    CommandBlocker.PULSE_HOLD_UNRESOLVED: "Pulse-versus-held command semantics are unresolved",
    CommandBlocker.EMERGENCY_APPROPRIATENESS_UNRESOLVED: "Software emergency shutdown appropriateness and exact semantics are unapproved",
}


class CommandCapability(BaseModel):
    command: LogicalCommand
    target: str
    available: Literal[False]
    blockers: list[CommandBlocker]
    reasons: list[str]


class CommandCapabilitiesResponse(BaseModel):
    capabilities: list[CommandCapability]
    execution_available: Literal[False] = False


def evaluate_contract(contract: CommandContract) -> CommandCapability:
    blockers = [
        CommandBlocker.EXECUTION_NOT_IMPLEMENTED,
        CommandBlocker.AUDIT_FAIL_CLOSED_NOT_IMPLEMENTED,
    ]
    checks = (
        (contract.plc_write_node_id is None, CommandBlocker.WRITE_NODE_UNRESOLVED),
        (contract.plc_write_type is None, CommandBlocker.WRITE_TYPE_UNRESOLVED),
        (
            contract.readback_node_id is None or contract.readback_semantics is None,
            CommandBlocker.READBACK_UNRESOLVED,
        ),
        (
            contract.acknowledgement_semantics is None,
            CommandBlocker.ACKNOWLEDGEMENT_UNRESOLVED,
        ),
        (
            contract.required_machine_preconditions is None,
            CommandBlocker.PRECONDITIONS_UNRESOLVED,
        ),
        (contract.authorization_policy is None, CommandBlocker.AUTHORIZATION_UNAPPROVED),
        (contract.confirmation_policy is None, CommandBlocker.CONFIRMATION_UNAPPROVED),
        (
            contract.controls_engineering_approval is None,
            CommandBlocker.CONTROLS_APPROVAL_UNRESOLVED,
        ),
        (
            contract.execution_timeout_seconds is None
            or contract.acknowledgement_timeout_seconds is None,
            CommandBlocker.TIMEOUT_UNRESOLVED,
        ),
        (contract.failure_semantics is None, CommandBlocker.FAILURE_BEHAVIOR_UNRESOLVED),
        (contract.network_loss_semantics is None, CommandBlocker.NETWORK_LOSS_UNRESOLVED),
        (
            contract.retry_policy is None or contract.idempotency_semantics is None,
            CommandBlocker.RETRY_IDEMPOTENCY_UNRESOLVED,
        ),
    )
    blockers.extend(blocker for unresolved, blocker in checks if unresolved)
    if contract.requested_value_type == RequestedValueType.NUMBER and (
        contract.allowed_min is None
        or contract.allowed_max is None
        or contract.engineering_unit is None
        or contract.scaling_semantics is None
        or contract.readback_tolerance is None
        or contract.settling_semantics is None
    ):
        blockers.append(CommandBlocker.RANGE_SCALING_UNRESOLVED)
    if contract.requested_value_type == RequestedValueType.BOOLEAN and (
        contract.allowed_values is None or contract.command_polarity is None
    ):
        blockers.append(CommandBlocker.POLARITY_UNRESOLVED)
    if contract.command in {
        LogicalCommand.PROTECTION_RESET,
        LogicalCommand.INTERLOCK_RESET,
    } and contract.pulse_or_hold_semantics is None:
        blockers.append(CommandBlocker.PULSE_HOLD_UNRESOLVED)
    if (
        contract.command == LogicalCommand.EMERGENCY_SHUTDOWN
        and contract.software_emergency_shutdown_approved is not True
    ):
        blockers.append(CommandBlocker.EMERGENCY_APPROPRIATENESS_UNRESOLVED)
    return CommandCapability(
        command=contract.command,
        target=contract.target,
        available=False,
        blockers=blockers,
        reasons=[BLOCKER_MESSAGES[blocker] for blocker in blockers],
    )


def phase4_capabilities() -> CommandCapabilitiesResponse:
    return CommandCapabilitiesResponse(
        capabilities=[evaluate_contract(contract) for contract in phase4_command_contracts()]
    )
