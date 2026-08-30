# OPC UA production commissioning matrix

> **THIS IS NOT A PRODUCTION NODE MAP.** It is non-executable commissioning preparation. Every candidate requires explicit verification and approval before being copied into a separately validated runtime production map.

- Template purpose: `production-template`
- Template status: `incomplete`
- Production ready: `false`
- PLC source confirmed: `14`
- Partially resolved: `2`
- Missing physical source: `8`
- Exported symbol confirmed: `15`
- Needs OPC UA discovery: `16`
- Runtime boundary: `APP_MODE=opcua_readonly` accepts only the independent strict `NodeMap` schema with `purpose=production`.

| Equipment | HMI field | Physical PLC source | PLC variable | Exported CODESYS symbol path | Exported? | Symbol access | Expected datatype | Native unit | HMI unit | Conversion | Confidence | NodeId discovered? | Remaining blockers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CMPS | state | %IX49.3 (Current CMPS state source) | di_IntS_CMPS_On_Raw<br>gIntS_Inp.CMPS_On | Application.GVL_IntS.gIntS_Inp.CMPS_On | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| CMPS | current | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | A | UNKNOWN | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| CMPS | interlock | %QX57.1 (PLC authorization/interlock output, not independent equipment feedback) | do_IntS_Auth_CMPS_Raw<br>gIntS_Outp.Auth_CMPS | Application.GVL_IntS.gIntS_Outp.Auth_CMPS | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| CFPS | state | %IX49.6 (Current CFPS state source) | di_IntS_CFPS_On_Raw<br>gIntS_Inp.CFPS_On | Application.GVL_IntS.gIntS_Inp.CFPS_On | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| CFPS | power | NOT PRESENT IN CURRENT PLC; related context only: %IW33 (Pf command/control feedback voltage; commissioning context only) | Fb_FilamentPower_V | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | W | UNKNOWN | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| CFPS | feedback | %IX52.5 (Primary generic CFPS run-feedback candidate)<br>%IX52.4 (Stabilization feedback context only) | di_CFPS_RunFb_Raw<br>filamentData.Sts_Run<br>di_CFPS_StabilizationFb_Raw<br>fbFilament.FbStabilize | Application.PLC_PRG.filamentData.Sts_Run | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | STRONGLY_INFERRED | NEEDS_NODE_ID_DISCOVERY | NEEDS_CONTROLS_VERIFICATION, NEEDS_NODE_ID_DISCOVERY, NEEDS_CONTROLS_APPROVAL_FOR_FIELD_SELECTION |
| CFPS | interlock | %QX58.3 (Current CFPS authorization output) | do_IntS_Auth_CFPS_Raw<br>gIntS_Outp.Auth_CFPS | Application.GVL_IntS.gIntS_Outp.Auth_CFPS | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| IPPS | state | %IX49.4 (Current IPPS state source) | di_IntS_IPPS_On_Raw<br>gIntS_Inp.IPPS_On | Application.GVL_IntS.gIntS_Inp.IPPS_On | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| IPPS | voltage | %IW27 (Underlying physical source; not the backend OPC UA candidate) | ai_IonPumpVoltage_Raw<br>daqData.IonPumpVoltage_kV | Application.PLC_PRG.daqData.IonPumpVoltage_kV | YES | Read | REAL | kV | V | scale=1000; offset=0 | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY, NEEDS_RANGE_APPROVAL, NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION |
| IPPS | current | %IW28 (Underlying physical source; not the backend OPC UA candidate) | ai_IonPumpCurrent_Raw<br>daqData.IonPumpCurrent_mA | Application.PLC_PRG.daqData.IonPumpCurrent_mA | YES | Read | REAL | mA | A | scale=0.001; offset=0 | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY, NEEDS_RANGE_APPROVAL, NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION |
| IPPS | interlock | %QX57.0 (Current IPPS authorization output) | do_IntS_Auth_IPPS_Raw<br>gIntS_Outp.Auth_IPPS | Application.GVL_IntS.gIntS_Outp.Auth_IPPS | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| ARC_DETECTOR | state | %IX50.4 (Exported generic Arc Alarm 1; raw TRUE = healthy/OK)<br>%IX50.5 (Exported generic Arc Alarm 2; raw FALSE = healthy/OK)<br>%IX51.1 (CPS Arc candidate within exported hvpsCpsIn)<br>%IX52.3 (APS Arc context within exported fbAPS) | di_IntS_ArcAlarm1_Raw<br>Application.GVL_IntS.gIntS_Inp.ArcAlarm1_OK<br>di_IntS_ArcAlarm2_Raw<br>Application.GVL_IntS.gIntS_Inp.ArcAlarm2_OK<br>Application.PLC_PRG.hvpsCpsIn.Arc<br>Application.PLC_PRG.fbAPS | UNKNOWN | NO | NOT APPLICABLE | BOOL candidates | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | UNKNOWN | NEEDS_NODE_ID_DISCOVERY | NEEDS_CONTROLS_VERIFICATION, NEEDS_NODE_ID_DISCOVERY, NEEDS_SIGNAL_SELECTION, NEEDS_AGGREGATION, NEEDS_LATCHING, NEEDS_RECOVERY_SEMANTICS, NEEDS_SEVERITY_APPROVAL |
| AHVPS | state | %IX50.1 (Direct confirmed AHVPS state source)<br>%IX52.0 (APS Ready supporting context)<br>%IX52.1 (APS Rectifier supporting context)<br>%IX51.7 (APS Charge supporting context) | di_IntS_APS_On_Raw<br>gIntS_Inp.APS_On | Application.GVL_IntS.gIntS_Inp.APS_On | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| AHVPS | voltage | NOT PRESENT IN CURRENT PLC; related context only: %QW27 (ANODE VOLTAGE SETPOINT command context only) | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | kV | UNKNOWN | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| AHVPS | protection | %IX52.2 (APS internal protection input)<br>%IX51.5 (APS overcurrent input)<br>%IX51.6 (APS overvoltage input)<br>%IX52.3 (APS arc input) | fbAPS.StatusFault<br>gAlarms.ApsFault | Application.GVL_Alarms.gAlarms.ApsFault | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| AHVPS | interlock | %QX56.1 (Current AHVPS/APS authorization output) | do_IntS_Auth_APS_Raw<br>gIntS_Outp.Auth_APS | Application.GVL_IntS.gIntS_Outp.Auth_APS | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| CHVPS | state | %IX50.0 (Direct confirmed CHVPS state source)<br>%IX50.6 (CPS Ready supporting context)<br>%IX50.7 (CPS Rectifier supporting context)<br>%IX51.4 (CPS Charge supporting context) | di_IntS_CPS_On_Raw<br>gIntS_Inp.CPS_On | Application.GVL_IntS.gIntS_Inp.CPS_On | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| CHVPS | voltage | NOT PRESENT IN CURRENT PLC; related context only: %QW24 (CATHODE VOLTAGE SETPOINT command context only) | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | kV | UNKNOWN | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| CHVPS | protection | %IX51.0 (CPS internal protection input)<br>%IX51.2 (CPS overcurrent input)<br>%IX51.3 (CPS overvoltage input)<br>%IX51.1 (CPS arc input) | fbCPS.StatusFault<br>gAlarms.CpsFault | Application.GVL_Alarms.gAlarms.CpsFault | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| CHVPS | interlock | %QX56.2 (Current CHVPS/CPS authorization output) | do_IntS_Auth_CPS_Raw<br>gIntS_Outp.Auth_CPS | Application.GVL_IntS.gIntS_Outp.Auth_CPS | YES | Read | BOOL | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | CONFIRMED | NEEDS_NODE_ID_DISCOVERY | NEEDS_NODE_ID_DISCOVERY |
| PULSE_GENERATOR | state | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| PULSE_GENERATOR | feedback | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | NOT APPLICABLE | NOT APPLICABLE | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| PULSE_GENERATOR | pulse_length | NOT PRESENT IN CURRENT PLC; related context only: %QW26 (Pulse-duration PRESET command-side context only) | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | ms | UNKNOWN | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |
| PULSE_GENERATOR | pulse_period | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NOT PRESENT IN CURRENT PLC | NO | NOT APPLICABLE | UNKNOWN | UNKNOWN | s | UNKNOWN | UNKNOWN | NOT APPLICABLE UNTIL SOURCE EXISTS | MISSING_PHYSICAL_SOURCE |

## Confirmed equipment identities

| Application equipment | PLC equipment | Meaning | Confidence | Approval | Provenance |
|---|---|---|---|---|---|
| AHVPS | APS | Anode Power Supply | CONFIRMED | APPROVED | Current offline PLC and equipment evidence establishes APS as the anode supply. |
| CHVPS | CPS | Cathode Power Supply | CONFIRMED | APPROVED | Current offline PLC and equipment evidence establishes CPS as the cathode supply. |

## Global commissioning issues

| Issue | Blocker | Affected signals | Resolution | Evidence |
|---|---|---|---|---|
| 750_471_process_representation | NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION | ipps.voltage, ipps.current | TBD | 750-471 #1 process-image WORD addresses are confirmed as %IW27, %IW28, %IW29 and %IW30.<br>750-471 #2 process-image WORD addresses are confirmed as %IW31, %IW32, %IW33 and %IW34.<br>Operator confirmation establishes 0-10 V electrical input mode for both modules.<br>Process-image datatype WORD is confirmed; exact numerical representation remains unresolved.<br>The PLC assumption raw / 32767 * 10 is not independently production-verified. |
| poor_vacuum_polarity | NEEDS_POLARITY_VERIFICATION | interlock.cfps | TBD | Equipment documentation says the bad-vacuum contact closes on fault.<br>Current PLC logic assigns PoorVacuum_OK := di_IntS_PoorVacuum_Raw.<br>Do not change PLC logic or silently resolve this conflict during metadata commissioning. |
| cfps_stabilization_polarity | NEEDS_POLARITY_VERIFICATION | cfps.feedback | TBD | %IX52.4 is di_CFPS_StabilizationFb_Raw.<br>Current PLC passes it directly to FbStabilize.<br>PLC_PRG explicitly requires physical-polarity verification against the installed supply. |

## Confirmed forbidden substitutes

| Application field | Physical address | PLC / exported symbol | Reason | Confidence |
|---|---|---|---|---|
| cfps.power | %IW33 | Application.PLC_PRG.filamentData.Fb_FilamentPower_V | Voltage command/control feedback is not authoritative actual filament power in W; the relationship is non-linear and no 70 W/V conversion is permitted. | CONFIRMED |
| chvps.voltage | %QW24 | Application.GVL_Setpoints.rSp_CathodeVolt_V | Cathode voltage preset is command-side and is not actual CHVPS voltage feedback. | CONFIRMED |
| ahvps.voltage | %QW27 | Application.GVL_Setpoints.rSp_AnodeVolt_V | Anode voltage preset is command-side and is not actual AHVPS voltage feedback. | CONFIRMED |
| pulse_generator.length | %QW26 | Application.GVL_Setpoints.rSp_PulseDuration_V | Pulse duration preset is command-side and is not actual pulse length feedback. | CONFIRMED |
| ipps.hv_active | NOT APPLICABLE | FbHvActive := FALSE | The constant software placeholder is not mapped physical IPPS HV-active feedback and is not an HMI telemetry field. | CONFIRMED |

## Common OPC UA configuration

All entries below remain unresolved and require controls-engineering approval. Non-local production OPC UA must use `SignAndEncrypt`; this document does not select a SecurityPolicy.

| Parameter | Value | Confidence | Approval | Note |
|---|---|---|---|---|
| endpoint | TBD | UNKNOWN | UNAPPROVED | Do not browse or infer the endpoint. |
| namespace_indexes | TBD | UNKNOWN | UNAPPROVED | Generated Symbol Configuration does not supply the live server namespace table; record it during authorized read-only discovery. |
| namespace_uris | TBD | UNKNOWN | UNAPPROVED | Generated Symbol Configuration does not supply the live server namespace table; record it during authorized read-only discovery. |
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
- The exported processed IPPS REAL symbols are selected; exact 750-471 WORD process representation still requires verification of the PLC engineering conversion.
- Arc aggregation, polarity, latching, recovery, and severity remain unresolved.
- Poor-vacuum physical polarity remains unresolved; current PLC logic must not be changed by this metadata task.
