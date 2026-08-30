# OPC UA production commissioning matrix

> **THIS IS NOT A PRODUCTION NODE MAP.** It is non-executable commissioning preparation. Every candidate requires explicit verification and approval before being copied into a separately validated runtime production map.

- Template purpose: `production-template`
- Template status: `incomplete`
- Production ready: `false`
- PLC source confirmed: `12`
- Partially resolved: `4`
- Missing physical source: `8`
- Needs OPC UA discovery: `16`
- Runtime boundary: `APP_MODE=opcua_readonly` accepts only the independent strict `NodeMap` schema with `purpose=production`.

| Equipment | Field | PLC logical candidate | Raw PLC symbol | Physical address | Datatype | Native representation / unit | HMI unit | Conversion state | Semantics | Confidence | Source classification | OPC UA discovery status | Commissioning blockers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CMPS | state | gIntS_Inp.CMPS_On (Current CMPS state source) | di_IntS_CMPS_On_Raw (Current CMPS state source) | %IX49.3 (Current CMPS state source) | BOOL (Current CMPS state source) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = CMPS ON; FALSE = CMPS OFF | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| CMPS | current | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | UNKNOWN | A | TBD | NOT APPLICABLE | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| CMPS | interlock | gIntS_Outp.Auth_CMPS (PLC authorization/interlock output, not independent equipment feedback) | do_IntS_Auth_CMPS_Raw (PLC authorization/interlock output, not independent equipment feedback) | %QX57.1 (PLC authorization/interlock output, not independent equipment feedback) | BOOL (PLC authorization/interlock output, not independent equipment feedback) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = PLC authorization granted; FALSE = authorization withheld | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| CFPS | state | gIntS_Inp.CFPS_On (Current CFPS state source) | di_IntS_CFPS_On_Raw (Current CFPS state source) | %IX49.6 (Current CFPS state source) | BOOL (Current CFPS state source) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = CFPS ON; FALSE = CFPS OFF | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| CFPS | power | NOT PRESENT IN CURRENT PLC; related context only: Fb_FilamentPower_V (Pf command/control feedback voltage; commissioning context only) | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC; related context only: %IW33 (Pf command/control feedback voltage; commissioning context only) | NOT PRESENT IN CURRENT PLC; related context only: WORD raw / REAL processed (Pf command/control feedback voltage; commissioning context only) | UNKNOWN | W | TBD | NOT APPLICABLE | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| CFPS | feedback | filamentData.Sts_Run (Primary generic CFPS run-feedback candidate) | di_CFPS_RunFb_Raw (Primary generic CFPS run-feedback candidate) | %IX52.5 (Primary generic CFPS run-feedback candidate)<br>%IX52.4 (Stabilization feedback context only) | BOOL (Primary generic CFPS run-feedback candidate)<br>BOOL (Stabilization feedback context only) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE likely means CFPS / IIPT running | STRONGLY_INFERRED | NEEDS_CONTROLS_VERIFICATION | NEEDS_OPCUA_DISCOVERY | NEEDS_CONTROLS_VERIFICATION, NEEDS_OPCUA_DISCOVERY |
| CFPS | interlock | gIntS_Outp.Auth_CFPS (Current CFPS authorization output) | do_IntS_Auth_CFPS_Raw (Current CFPS authorization output) | %QX58.3 (Current CFPS authorization output) | BOOL (Current CFPS authorization output) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = authorization granted; FALSE = authorization withheld | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| IPPS | state | ippsData.Sts_On / gIntS_Inp.IPPS_On (Current IPPS state source) | di_IntS_IPPS_On_Raw (Current IPPS state source) | %IX49.4 (Current IPPS state source) | BOOL (Current IPPS state source) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = IPPS ON; FALSE = IPPS OFF | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| IPPS | voltage | ai_IonPumpVoltage_Raw (Confirmed raw PLC source)<br>ippsData.Meas_Voltage_kV (Confirmed processed PLC candidate) | UNKNOWN | %IW27 (Confirmed raw PLC source) | WORD (Confirmed raw PLC source)<br>REAL (Confirmed processed PLC candidate) | raw process image / kV | V | Processed REAL kV x 1000 = HMI V; raw conversion awaits 750-471 parameterization | NOT APPLICABLE | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY, NEEDS_RANGE_APPROVAL, NEEDS_EXPORTED_SYMBOL_SELECTION, NEEDS_750_471_CONFIGURATION |
| IPPS | current | ai_IonPumpCurrent_Raw (Confirmed raw PLC source)<br>ippsData.Meas_Current_mA (Confirmed processed PLC candidate) | UNKNOWN | %IW28 (Confirmed raw PLC source) | WORD (Confirmed raw PLC source)<br>REAL (Confirmed processed PLC candidate) | raw process image / mA | A | Processed REAL mA / 1000 = HMI A; raw conversion awaits 750-471 parameterization | NOT APPLICABLE | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY, NEEDS_RANGE_APPROVAL, NEEDS_EXPORTED_SYMBOL_SELECTION, NEEDS_750_471_CONFIGURATION |
| IPPS | interlock | gIntS_Outp.Auth_IPPS (Current IPPS authorization output) | do_IntS_Auth_IPPS_Raw (Current IPPS authorization output) | %QX57.0 (Current IPPS authorization output) | BOOL (Current IPPS authorization output) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = authorization granted; FALSE = authorization withheld | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| ARC_DETECTOR | state | UNKNOWN | UNKNOWN | %IX50.4 (Generic Arc Alarm 1; raw TRUE = healthy/OK)<br>%IX50.5 (Generic Arc Alarm 2; raw FALSE = healthy/OK)<br>%IX51.1 (CPS Arc candidate)<br>%IX52.3 (APS Arc candidate) | BOOL (Generic Arc Alarm 1; raw TRUE = healthy/OK)<br>BOOL (Generic Arc Alarm 2; raw FALSE = healthy/OK)<br>BOOL (CPS Arc candidate)<br>BOOL (APS Arc candidate) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | NEEDS VERIFICATION | UNKNOWN | NEEDS_CONTROLS_VERIFICATION | NEEDS_OPCUA_DISCOVERY | NEEDS_CONTROLS_VERIFICATION, NEEDS_OPCUA_DISCOVERY, NEEDS_SIGNAL_SELECTION, NEEDS_AGGREGATION, NEEDS_LATCHING, NEEDS_RECOVERY_SEMANTICS, NEEDS_SEVERITY_APPROVAL |
| AHVPS | state | gIntS_Inp.APS_On (Direct confirmed AHVPS state source) | di_IntS_APS_On_Raw (Direct confirmed AHVPS state source) | %IX50.1 (Direct confirmed AHVPS state source)<br>%IX52.0 (APS Ready supporting context)<br>%IX52.1 (APS Rectifier supporting context)<br>%IX51.7 (APS Charge supporting context) | BOOL (Direct confirmed AHVPS state source)<br>BOOL (APS Ready supporting context)<br>BOOL (APS Rectifier supporting context)<br>BOOL (APS Charge supporting context) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = Anode Power Supply ON; FALSE = OFF | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| AHVPS | voltage | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC; related context only: %QW27 (ANODE VOLTAGE SETPOINT command context only) | NOT PRESENT IN CURRENT PLC; related context only: WORD (ANODE VOLTAGE SETPOINT command context only) | UNKNOWN | kV | TBD | NOT APPLICABLE | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| AHVPS | protection | PLC_PRG.fbAPS.StatusFault (Likely aggregate protection candidate) | UNKNOWN | %IX52.2 (APS internal protection input)<br>%IX51.5 (APS overcurrent input)<br>%IX51.6 (APS overvoltage input)<br>%IX52.3 (APS arc input) | BOOL (Likely aggregate protection candidate)<br>BOOL (APS internal protection input)<br>BOOL (APS overcurrent input)<br>BOOL (APS overvoltage input)<br>BOOL (APS arc input) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | NEEDS VERIFICATION | STRONGLY_INFERRED | NEEDS_CONTROLS_VERIFICATION | NEEDS_OPCUA_DISCOVERY | NEEDS_CONTROLS_VERIFICATION, NEEDS_OPCUA_DISCOVERY, NEEDS_CURRENT_FB_VERIFICATION |
| AHVPS | interlock | gIntS_Outp.Auth_APS (Current AHVPS/APS authorization output) | do_IntS_Auth_APS_Raw (Current AHVPS/APS authorization output) | %QX56.1 (Current AHVPS/APS authorization output) | BOOL (Current AHVPS/APS authorization output) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = APS/anode authorization granted; FALSE = withheld | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| CHVPS | state | gIntS_Inp.CPS_On (Direct confirmed CHVPS state source) | di_IntS_CPS_On_Raw (Direct confirmed CHVPS state source) | %IX50.0 (Direct confirmed CHVPS state source)<br>%IX50.6 (CPS Ready supporting context)<br>%IX50.7 (CPS Rectifier supporting context)<br>%IX51.4 (CPS Charge supporting context) | BOOL (Direct confirmed CHVPS state source)<br>BOOL (CPS Ready supporting context)<br>BOOL (CPS Rectifier supporting context)<br>BOOL (CPS Charge supporting context) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = Cathode Power Supply ON; FALSE = OFF | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| CHVPS | voltage | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC; related context only: %QW24 (CATHODE VOLTAGE SETPOINT command context only) | NOT PRESENT IN CURRENT PLC; related context only: WORD (CATHODE VOLTAGE SETPOINT command context only) | UNKNOWN | kV | TBD | NOT APPLICABLE | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| CHVPS | protection | PLC_PRG.fbCPS.StatusFault (Likely aggregate protection candidate) | UNKNOWN | %IX51.0 (CPS internal protection input)<br>%IX51.2 (CPS overcurrent input)<br>%IX51.3 (CPS overvoltage input)<br>%IX51.1 (CPS arc input) | BOOL (Likely aggregate protection candidate)<br>BOOL (CPS internal protection input)<br>BOOL (CPS overcurrent input)<br>BOOL (CPS overvoltage input)<br>BOOL (CPS arc input) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | NEEDS VERIFICATION | STRONGLY_INFERRED | NEEDS_CONTROLS_VERIFICATION | NEEDS_OPCUA_DISCOVERY | NEEDS_CONTROLS_VERIFICATION, NEEDS_OPCUA_DISCOVERY, NEEDS_CURRENT_FB_VERIFICATION |
| CHVPS | interlock | gIntS_Outp.Auth_CPS (Current CHVPS/CPS authorization output) | do_IntS_Auth_CPS_Raw (Current CHVPS/CPS authorization output) | %QX56.2 (Current CHVPS/CPS authorization output) | BOOL (Current CHVPS/CPS authorization output) | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | TRUE = CPS/cathode authorization granted; FALSE = withheld | CONFIRMED | PLC_SOURCE_CONFIRMED | NEEDS_OPCUA_DISCOVERY | NEEDS_OPCUA_DISCOVERY |
| PULSE_GENERATOR | state | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | NEEDS VERIFICATION | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| PULSE_GENERATOR | feedback | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | NEEDS VERIFICATION | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| PULSE_GENERATOR | pulse_length | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC; related context only: %QW26 (Pulse-duration PRESET command-side context only) | NOT PRESENT IN CURRENT PLC; related context only: WORD (Pulse-duration PRESET command-side context only) | UNKNOWN | ms | TBD | NOT APPLICABLE | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| PULSE_GENERATOR | pulse_period | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | UNKNOWN | s | TBD | NOT APPLICABLE | UNKNOWN | MISSING_PHYSICAL_SOURCE | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |

## Confirmed equipment identities

| Application equipment | PLC equipment | Meaning | Confidence | Approval | Provenance |
|---|---|---|---|---|---|
| AHVPS | APS | Anode Power Supply | CONFIRMED | APPROVED | Current offline PLC and equipment evidence establishes APS as the anode supply. |
| CHVPS | CPS | Cathode Power Supply | CONFIRMED | APPROVED | Current offline PLC and equipment evidence establishes CPS as the cathode supply. |

## Global commissioning issues

| Issue | Blocker | Affected signals | Resolution | Evidence |
|---|---|---|---|---|
| 750_471_parameterization | NEEDS_750_471_CONFIGURATION | ipps.voltage, ipps.current, cfps.power | TBD | 750-471 #1 process-image WORD addresses are confirmed as %IW27, %IW28, %IW29 and %IW30.<br>750-471 #2 process-image WORD addresses are confirmed as %IW31, %IW32, %IW33 and %IW34.<br>Input mode, raw representation, status/control format, filter, signedness and exact 0..10 V representation remain unresolved.<br>raw / 32767 * 10 is not production-approved without the parameter pages. |
| poor_vacuum_polarity | NEEDS_POLARITY_VERIFICATION | interlock.cfps | TBD | Equipment documentation says the bad-vacuum contact closes on fault.<br>Current PLC logic assigns PoorVacuum_OK := di_IntS_PoorVacuum_Raw.<br>Do not change PLC logic or silently resolve this conflict during metadata commissioning. |

## Common OPC UA configuration

All entries below remain unresolved and require controls-engineering approval. Non-local production OPC UA must use `SignAndEncrypt`; this document does not select a SecurityPolicy.

| Parameter | Value | Confidence | Approval | Note |
|---|---|---|---|---|
| endpoint | TBD | UNKNOWN | UNAPPROVED | Do not browse or infer the endpoint. |
| namespace_indexes | TBD | UNKNOWN | UNAPPROVED | CODESYS OPC UA Symbol Configuration has not been obtained. |
| namespace_uris | TBD | UNKNOWN | UNAPPROVED | CODESYS OPC UA Symbol Configuration has not been obtained. |
| node_id_style | TBD | UNKNOWN | UNAPPROVED | Production identifier representation is unknown. |
| security_policy | TBD | UNKNOWN | UNAPPROVED | Non-local production OPC UA must use SignAndEncrypt. |
| trusted_server_certificate_identity | TBD | UNKNOWN | UNAPPROVED | Trusted PLC server identity has not been supplied. |
| authentication_method | TBD | UNKNOWN | UNAPPROVED | Production authentication method is unapproved. |
| dedicated_read_only_account | TBD | UNKNOWN | UNAPPROVED | Dedicated read-only account has not been provisioned. |
| source_timestamp_behavior | TBD | UNKNOWN | UNAPPROVED | PLC SourceTimestamp behavior has not been verified. |
| engineering_unit_metadata | TBD | UNKNOWN | UNAPPROVED | Authority and availability of server engineering-unit metadata is unknown. |

## Commissioning rules

- `STRONGLY_INFERRED` and `WEAKLY_INFERRED` are never production approval.
- Setpoint outputs `%QW27`, `%QW24`, and `%QW26` are command-side context only and must not be used as actual readbacks.
- The CFPS voltage-to-power relationship is unresolved and non-linear; no guessed W/V conversion is permitted.
- Raw versus converted IPPS symbols must be selected only after inspecting the CODESYS OPC UA Symbol Configuration and verifying the 750-471 process-image mode.
- Arc aggregation, polarity, latching, recovery, and severity remain unresolved.
- Poor-vacuum physical polarity remains unresolved; current PLC logic must not be changed by this metadata task.
