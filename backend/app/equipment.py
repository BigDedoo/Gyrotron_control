from collections.abc import Iterable
from datetime import datetime

from app.models import (
    AlarmSeverity,
    ArcDetectorEquipmentStatus,
    CFPSEquipmentStatus,
    CMPSEquipmentStatus,
    DataSource,
    DataState,
    EquipmentId,
    EquipmentSnapshot,
    HVPSEquipmentStatus,
    HVPSSupplyEquipmentStatus,
    IPPSEquipmentStatus,
    InterpretedState,
    MappingCoverage,
    PulseGeneratorEquipmentStatus,
    SignalQuality,
    SignalValue,
    StateSignalValue,
)
from app.opcua.node_map import (
    EQUIPMENT_SIGNAL_UNITS,
    LogicalSignal,
    LogicalStateSignal,
    state_signal_group,
    state_signal_label,
)


EQUIPMENT_STATE_SIGNALS = {
    LogicalStateSignal.CMPS_STATE: EquipmentId.CMPS,
    LogicalStateSignal.CMPS: EquipmentId.CMPS,
    LogicalStateSignal.CFPS_STATE: EquipmentId.CFPS,
    LogicalStateSignal.CFPS_FEEDBACK: EquipmentId.CFPS,
    LogicalStateSignal.CFPS_INTERLOCK: EquipmentId.CFPS,
    LogicalStateSignal.IPPS_STATE: EquipmentId.IPPS,
    LogicalStateSignal.IPPS: EquipmentId.IPPS,
    LogicalStateSignal.ARC_DETECTOR: EquipmentId.ARC_DETECTOR,
    LogicalStateSignal.AHVPS_STATE: EquipmentId.AHVPS,
    LogicalStateSignal.AHVPS_PROTECTION: EquipmentId.AHVPS,
    LogicalStateSignal.AHVPS_INTERLOCK: EquipmentId.AHVPS,
    LogicalStateSignal.CHVPS_STATE: EquipmentId.CHVPS,
    LogicalStateSignal.CHVPS_PROTECTION: EquipmentId.CHVPS,
    LogicalStateSignal.CHVPS_INTERLOCK: EquipmentId.CHVPS,
    LogicalStateSignal.PULSE_GENERATOR_STATE: EquipmentId.PULSE_GENERATOR,
    LogicalStateSignal.PULSE_GENERATOR_FEEDBACK: EquipmentId.PULSE_GENERATOR,
}


def _unmapped_reading(signal: LogicalSignal, source: DataSource) -> SignalValue:
    return SignalValue(
        value=None,
        unit=EQUIPMENT_SIGNAL_UNITS[signal],
        quality=SignalQuality.UNAVAILABLE,
        source_timestamp=None,
        observed_at=None,
        mapped=False,
    )


def _unmapped_state(signal: LogicalStateSignal, source: DataSource) -> StateSignalValue:
    return StateSignalValue(
        logical_name=signal.value,
        display_name=state_signal_label(signal),
        group=state_signal_group(signal),
        mapped=False,
        raw_value=None,
        interpreted_state=InterpretedState.UNKNOWN,
        quality=SignalQuality.UNAVAILABLE,
        source_timestamp=None,
        observed_at=None,
        source=source,
        data_state=DataState.UNAVAILABLE,
        equipment=EQUIPMENT_STATE_SIGNALS.get(signal),
    )


def _effective_state(
    sample: StateSignalValue,
    data_state: DataState,
) -> StateSignalValue:
    updates = {}
    if sample.equipment is None:
        updates["equipment"] = EQUIPMENT_STATE_SIGNALS.get(
            LogicalStateSignal(sample.logical_name)
        )
    if data_state in {DataState.STALE, DataState.UNAVAILABLE}:
        updates.update(
            interpreted_state=InterpretedState.UNKNOWN,
            data_state=data_state,
        )
    elif sample.quality != SignalQuality.GOOD:
        updates["interpreted_state"] = InterpretedState.UNKNOWN
    return sample.model_copy(update=updates) if updates else sample


def _effective_reading(
    sample: SignalValue,
    data_state: DataState,
) -> SignalValue:
    if not sample.mapped:
        return sample
    if data_state == DataState.UNAVAILABLE:
        return sample.model_copy(
            update={
                "value": None,
                "quality": SignalQuality.UNAVAILABLE,
                "source_timestamp": None,
            }
        )
    if data_state == DataState.STALE and sample.quality == SignalQuality.GOOD:
        return sample.model_copy(update={"quality": SignalQuality.UNCERTAIN})
    return sample


def _quality(samples: Iterable[SignalValue | StateSignalValue]) -> SignalQuality:
    qualities = {sample.quality for sample in samples}
    for quality in (
        SignalQuality.BAD,
        SignalQuality.UNAVAILABLE,
        SignalQuality.UNCERTAIN,
    ):
        if quality in qualities:
            return quality
    return SignalQuality.GOOD


def _equipment_data_state(
    samples: Iterable[SignalValue | StateSignalValue],
    snapshot_data_state: DataState,
) -> DataState:
    if snapshot_data_state in {DataState.STALE, DataState.UNAVAILABLE}:
        return snapshot_data_state
    values = tuple(samples)
    if all(not sample.mapped for sample in values):
        return DataState.UNAVAILABLE
    if any(
        not sample.mapped
        or sample.quality != SignalQuality.GOOD
        or (isinstance(sample, SignalValue) and sample.value is None)
        or (
            isinstance(sample, StateSignalValue)
            and sample.interpreted_state == InterpretedState.UNKNOWN
        )
        for sample in values
    ):
        return DataState.DEGRADED
    return DataState.LIVE


def _status_fields(
    state: StateSignalValue,
    samples: Iterable[SignalValue | StateSignalValue],
    data_state: DataState,
) -> dict:
    values = (state, *tuple(samples))
    return {
        "state": state,
        "quality": _quality(values),
        "data_state": _equipment_data_state(values, data_state),
    }


def _trustworthy(sample: SignalValue | StateSignalValue) -> bool:
    if not sample.mapped or sample.quality != SignalQuality.GOOD:
        return False
    if isinstance(sample, SignalValue):
        return sample.value is not None
    return (
        sample.data_state == DataState.LIVE
        and sample.interpreted_state != InterpretedState.UNKNOWN
    )


def _contract_samples(snapshot: EquipmentSnapshot):
    yield "cmps.state", snapshot.cmps.state
    yield "cmps.current", snapshot.cmps.current
    yield "interlock.cmps", snapshot.cmps.interlock
    yield "cfps.state", snapshot.cfps.state
    yield "cfps.power", snapshot.cfps.power
    yield "cfps.feedback", snapshot.cfps.feedback
    yield "interlock.cfps", snapshot.cfps.interlock
    yield "ipps.state", snapshot.ipps.state
    yield "ipps.voltage", snapshot.ipps.voltage
    yield "ipps.current", snapshot.ipps.current
    yield "interlock.ipps", snapshot.ipps.interlock
    yield "alarm.arc_detector", snapshot.arc_detector.state
    yield "ahvps.state", snapshot.hvps.ahvps.state
    yield "ahvps.voltage", snapshot.hvps.ahvps.voltage
    yield "ahvps.protection", snapshot.hvps.ahvps.protection
    yield "interlock.ahvps", snapshot.hvps.ahvps.interlock
    yield "chvps.state", snapshot.hvps.chvps.state
    yield "chvps.voltage", snapshot.hvps.chvps.voltage
    yield "chvps.protection", snapshot.hvps.chvps.protection
    yield "interlock.chvps", snapshot.hvps.chvps.interlock
    yield "pulse_generator.state", snapshot.pulse_generator.state
    yield "pulse_generator.length", snapshot.pulse_generator.pulse_length
    yield "pulse_generator.period", snapshot.pulse_generator.pulse_period
    yield "pulse_generator.feedback", snapshot.pulse_generator.feedback


def _coverage(snapshot: EquipmentSnapshot) -> MappingCoverage:
    samples = tuple(_contract_samples(snapshot))
    missing = [name for name, sample in samples if not sample.mapped]
    unavailable = [
        name
        for name, sample in samples
        if sample.mapped and not _trustworthy(sample)
    ]
    trustworthy = sum(_trustworthy(sample) for _, sample in samples)
    return MappingCoverage(
        total=len(samples),
        mapped=len(samples) - len(missing),
        trustworthy=trustworthy,
        complete=not missing and not unavailable,
        missing=missing,
        unavailable=unavailable,
    )


def build_equipment_snapshot(
    *,
    source: DataSource,
    timestamp: datetime,
    sequence: int,
    data_state: DataState,
    readings: dict[LogicalSignal, SignalValue],
    state_signals: dict[LogicalStateSignal, StateSignalValue],
) -> EquipmentSnapshot:
    def reading(signal: LogicalSignal) -> SignalValue:
        return _effective_reading(
            readings.get(signal) or _unmapped_reading(signal, source),
            data_state,
        )

    def state(signal: LogicalStateSignal) -> StateSignalValue:
        return _effective_state(
            state_signals.get(signal) or _unmapped_state(signal, source),
            data_state,
        )

    cmps_state = state(LogicalStateSignal.CMPS_STATE)
    cmps_current = reading(LogicalSignal.CMPS_CURRENT)
    cmps_interlock = state(LogicalStateSignal.CMPS)
    cmps = CMPSEquipmentStatus(
        **_status_fields(cmps_state, (cmps_current, cmps_interlock), data_state),
        current=cmps_current,
        interlock=cmps_interlock,
    )

    cfps_state = state(LogicalStateSignal.CFPS_STATE)
    cfps_power = reading(LogicalSignal.CFPS_POWER)
    cfps_feedback = state(LogicalStateSignal.CFPS_FEEDBACK)
    cfps_interlock = state(LogicalStateSignal.CFPS_INTERLOCK)
    cfps = CFPSEquipmentStatus(
        **_status_fields(
            cfps_state,
            (cfps_power, cfps_feedback, cfps_interlock),
            data_state,
        ),
        power=cfps_power,
        feedback=cfps_feedback,
        interlock=cfps_interlock,
    )

    ipps_state = state(LogicalStateSignal.IPPS_STATE)
    ipps_voltage = reading(LogicalSignal.IPPS_VOLTAGE)
    ipps_current = reading(LogicalSignal.IPPS_CURRENT)
    ipps_interlock = state(LogicalStateSignal.IPPS)
    ipps = IPPSEquipmentStatus(
        **_status_fields(
            ipps_state,
            (ipps_voltage, ipps_current, ipps_interlock),
            data_state,
        ),
        voltage=ipps_voltage,
        current=ipps_current,
        interlock=ipps_interlock,
    )

    arc_state = state(LogicalStateSignal.ARC_DETECTOR)
    arc_detector = ArcDetectorEquipmentStatus(
        **_status_fields(arc_state, (), data_state),
        severity=arc_state.severity,
    )

    ahvps_state = state(LogicalStateSignal.AHVPS_STATE)
    ahvps_voltage = reading(LogicalSignal.AHVPS_VOLTAGE)
    ahvps_protection = state(LogicalStateSignal.AHVPS_PROTECTION)
    ahvps_interlock = state(LogicalStateSignal.AHVPS_INTERLOCK)
    ahvps = HVPSSupplyEquipmentStatus(
        **_status_fields(
            ahvps_state,
            (ahvps_voltage, ahvps_protection, ahvps_interlock),
            data_state,
        ),
        voltage=ahvps_voltage,
        protection=ahvps_protection,
        interlock=ahvps_interlock,
    )

    chvps_state = state(LogicalStateSignal.CHVPS_STATE)
    chvps_voltage = reading(LogicalSignal.CHVPS_VOLTAGE)
    chvps_protection = state(LogicalStateSignal.CHVPS_PROTECTION)
    chvps_interlock = state(LogicalStateSignal.CHVPS_INTERLOCK)
    chvps = HVPSSupplyEquipmentStatus(
        **_status_fields(
            chvps_state,
            (chvps_voltage, chvps_protection, chvps_interlock),
            data_state,
        ),
        voltage=chvps_voltage,
        protection=chvps_protection,
        interlock=chvps_interlock,
    )

    pulse_state = state(LogicalStateSignal.PULSE_GENERATOR_STATE)
    pulse_length = reading(LogicalSignal.PULSE_LENGTH)
    pulse_period = reading(LogicalSignal.PULSE_PERIOD)
    pulse_feedback = state(LogicalStateSignal.PULSE_GENERATOR_FEEDBACK)
    pulse_generator = PulseGeneratorEquipmentStatus(
        **_status_fields(
            pulse_state,
            (pulse_length, pulse_period, pulse_feedback),
            data_state,
        ),
        pulse_length=pulse_length,
        pulse_period=pulse_period,
        feedback=pulse_feedback,
    )

    snapshot = EquipmentSnapshot(
        timestamp=timestamp,
        source=source,
        sequence=sequence,
        data_state=data_state,
        cmps=cmps,
        cfps=cfps,
        ipps=ipps,
        arc_detector=arc_detector,
        hvps=HVPSEquipmentStatus(ahvps=ahvps, chvps=chvps),
        pulse_generator=pulse_generator,
        coverage=MappingCoverage(
            total=0,
            mapped=0,
            trustworthy=0,
            complete=False,
            missing=[],
        ),
    )
    return snapshot.model_copy(update={"coverage": _coverage(snapshot)})


def equipment_snapshot_with_data_state(
    snapshot: EquipmentSnapshot,
    data_state: DataState,
) -> EquipmentSnapshot:
    if data_state == snapshot.data_state:
        return snapshot
    readings = {
        LogicalSignal.CMPS_CURRENT: snapshot.cmps.current,
        LogicalSignal.CFPS_POWER: snapshot.cfps.power,
        LogicalSignal.IPPS_VOLTAGE: snapshot.ipps.voltage,
        LogicalSignal.IPPS_CURRENT: snapshot.ipps.current,
        LogicalSignal.AHVPS_VOLTAGE: snapshot.hvps.ahvps.voltage,
        LogicalSignal.CHVPS_VOLTAGE: snapshot.hvps.chvps.voltage,
        LogicalSignal.PULSE_LENGTH: snapshot.pulse_generator.pulse_length,
        LogicalSignal.PULSE_PERIOD: snapshot.pulse_generator.pulse_period,
    }
    states = {
        LogicalStateSignal.CMPS_STATE: snapshot.cmps.state,
        LogicalStateSignal.CMPS: snapshot.cmps.interlock,
        LogicalStateSignal.CFPS_STATE: snapshot.cfps.state,
        LogicalStateSignal.CFPS_FEEDBACK: snapshot.cfps.feedback,
        LogicalStateSignal.CFPS_INTERLOCK: snapshot.cfps.interlock,
        LogicalStateSignal.IPPS_STATE: snapshot.ipps.state,
        LogicalStateSignal.IPPS: snapshot.ipps.interlock,
        LogicalStateSignal.ARC_DETECTOR: snapshot.arc_detector.state,
        LogicalStateSignal.AHVPS_STATE: snapshot.hvps.ahvps.state,
        LogicalStateSignal.AHVPS_PROTECTION: snapshot.hvps.ahvps.protection,
        LogicalStateSignal.AHVPS_INTERLOCK: snapshot.hvps.ahvps.interlock,
        LogicalStateSignal.CHVPS_STATE: snapshot.hvps.chvps.state,
        LogicalStateSignal.CHVPS_PROTECTION: snapshot.hvps.chvps.protection,
        LogicalStateSignal.CHVPS_INTERLOCK: snapshot.hvps.chvps.interlock,
        LogicalStateSignal.PULSE_GENERATOR_STATE: snapshot.pulse_generator.state,
        LogicalStateSignal.PULSE_GENERATOR_FEEDBACK: snapshot.pulse_generator.feedback,
    }
    return build_equipment_snapshot(
        source=snapshot.source,
        timestamp=snapshot.timestamp,
        sequence=snapshot.sequence,
        data_state=data_state,
        readings=readings,
        state_signals=states,
    )
