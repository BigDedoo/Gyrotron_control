# OPC UA production commissioning matrix

> **THIS IS NOT A PRODUCTION NODE MAP.** It is non-executable commissioning preparation. Every candidate requires explicit verification and approval before being copied into a separately validated runtime production map.

- Template purpose: `production-template`
- Template status: `incomplete`
- Production ready: `false`
- Runtime boundary: `APP_MODE=opcua_readonly` accepts only the independent strict `NodeMap` schema with `purpose=production`.

| Equipment | Field | PLC candidate | NodeId | PLC type | Native unit | HMI unit | Conversion | Interpretation | Confidence | Missing |
|---|---|---|---|---|---|---|---|---|---|---|
| CMPS | state | %IX49.3 / di_IntS_CMPS_On_Raw (CMPS on-state input; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=on; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION |
| CMPS | current | TBD | TBD | TBD | TBD | A | TBD | TBD | UNKNOWN | BLOCKED_BY_PHYSICAL_SOURCE, NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE |
| CMPS | interlock | %QX57.1 / do_IntS_Auth_CMPS_Raw (CMPS authorization/interlock condition; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=ok; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY |
| CFPS | state | %IX49.6 / di_IntS_CFPS_On_Raw (CFPS on-state input; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=on; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION |
| CFPS | power | %IW33 / Fb_FilamentPower_V (CFPS feedback-voltage candidate; WORD raw / REAL converted, V) | TBD | WORD raw / REAL after PLC conversion | feedback voltage (V) | W | TBD | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE |
| CFPS | feedback | %IX52.5 / di_CFPS_RunFb_Raw (Primary generic CFPS run feedback candidate; BOOL)<br>%IX52.4 (Stabilization feedback context; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=ok; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION |
| CFPS | interlock | %QX58.3 / do_IntS_Auth_CFPS_Raw (CFPS authorization/interlock condition; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=ok; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY |
| IPPS | state | %IX49.4 / di_IntS_IPPS_On_Raw (IPPS on-state input; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=on; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION |
| IPPS | voltage | %IW27 (Raw IPPS voltage source candidate; WORD, raw process image)<br>Meas_Voltage_kV (Converted IPPS voltage source candidate; REAL, kV) | TBD | TBD | TBD | V | Converted candidate would require kV x 1000 -> V; raw WORD conversion remains channel-mode dependent | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE, NEEDS_SIGNAL_SELECTION |
| IPPS | current | %IW28 (Raw IPPS current source candidate; WORD, raw process image)<br>Meas_Current_mA (Converted IPPS current source candidate; REAL, mA) | TBD | TBD | TBD | A | Converted candidate would require mA / 1000 -> A; raw WORD conversion remains channel-mode dependent | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE, NEEDS_SIGNAL_SELECTION |
| IPPS | interlock | %QX57.0 / do_IntS_Auth_IPPS_Raw (IPPS authorization/interlock condition; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=ok; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY |
| ARC_DETECTOR | state | %IX50.4 (Generic Arc Alarm 1 candidate; BOOL)<br>%IX50.5 (Generic Arc Alarm 2 candidate; BOOL)<br>%IX51.1 (CPS Arc candidate; BOOL)<br>%IX52.3 (APS Arc candidate; BOOL) | TBD | TBD | TBD | NOT APPLICABLE | TBD | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY, NEEDS_SIGNAL_SELECTION, NEEDS_AGGREGATION, NEEDS_LATCHING, NEEDS_RECOVERY_SEMANTICS, NEEDS_SEVERITY |
| AHVPS | state | %IX50.1 (Primary APS overall-state candidate; BOOL)<br>%IX52.0 (APS ready supporting candidate; BOOL)<br>%IX52.1 (APS rectifier supporting candidate; BOOL)<br>%IX51.7 (APS charge supporting candidate; BOOL) | TBD | BOOL candidates | TBD | NOT APPLICABLE | TBD | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_SIGNAL_SELECTION |
| AHVPS | voltage | %QW27 (Command-side APS voltage setpoint context only; WORD) | TBD | TBD | TBD | kV | TBD | TBD | CONFIRMED | BLOCKED_BY_PHYSICAL_SOURCE, NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE |
| AHVPS | protection | %IX52.2 (APS internal protection candidate; BOOL)<br>%IX51.5 (APS overcurrent candidate; BOOL)<br>%IX51.6 (APS overvoltage candidate; BOOL)<br>%IX52.3 (APS arc candidate; BOOL)<br>fbAPS.StatusFault (Possible CODESYS aggregate; BOOL) | TBD | BOOL candidates | TBD | NOT APPLICABLE | TBD | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY, NEEDS_SIGNAL_SELECTION, NEEDS_AGGREGATION |
| AHVPS | interlock | %QX56.1 / Auth_APS (AHVPS/APS authorization candidate; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=ok; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY |
| CHVPS | state | %IX50.0 (Primary CPS overall-state candidate; BOOL)<br>%IX50.6 (CPS ready supporting candidate; BOOL)<br>%IX50.7 (CPS rectifier supporting candidate; BOOL)<br>%IX51.4 (CPS charge supporting candidate; BOOL) | TBD | BOOL candidates | TBD | NOT APPLICABLE | TBD | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_SIGNAL_SELECTION |
| CHVPS | voltage | %QW24 (Command-side CPS voltage setpoint context only; WORD) | TBD | TBD | TBD | kV | TBD | TBD | CONFIRMED | BLOCKED_BY_PHYSICAL_SOURCE, NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE, NEEDS_POLARITY |
| CHVPS | protection | %IX51.0 (CPS internal protection candidate; BOOL)<br>%IX51.2 (CPS overcurrent candidate; BOOL)<br>%IX51.3 (CPS overvoltage candidate; BOOL)<br>%IX51.1 (CPS arc candidate; BOOL)<br>fbCPS.StatusFault (Possible CODESYS aggregate; BOOL) | TBD | BOOL candidates | TBD | NOT APPLICABLE | TBD | TBD | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY, NEEDS_SIGNAL_SELECTION, NEEDS_AGGREGATION |
| CHVPS | interlock | %QX56.2 / Auth_CPS (CHVPS/CPS authorization candidate; BOOL) | TBD | BOOL | TBD | NOT APPLICABLE | TBD | true=ok; false=unresolved | STRONGLY_INFERRED | NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION, NEEDS_POLARITY |
| PULSE_GENERATOR | state | TBD | TBD | TBD | TBD | NOT APPLICABLE | TBD | TBD | UNKNOWN | BLOCKED_BY_PHYSICAL_SOURCE, NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION |
| PULSE_GENERATOR | feedback | TBD | TBD | TBD | TBD | NOT APPLICABLE | TBD | TBD | UNKNOWN | BLOCKED_BY_PHYSICAL_SOURCE, NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_INTERPRETATION |
| PULSE_GENERATOR | pulse_length | %QW26 (Command-side pulse-duration preset context only; WORD) | TBD | TBD | TBD | ms | TBD | TBD | CONFIRMED | BLOCKED_BY_PHYSICAL_SOURCE, NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE |
| PULSE_GENERATOR | pulse_period | TBD | TBD | TBD | TBD | s | TBD | TBD | UNKNOWN | BLOCKED_BY_PHYSICAL_SOURCE, NEEDS_NODE_ID, NEEDS_TYPE, NEEDS_CONVERSION, NEEDS_RANGE |

## Common OPC UA configuration

All entries below remain unresolved and require controls-engineering approval. Non-local production OPC UA must use `SignAndEncrypt`; this document does not select a SecurityPolicy.

| Parameter | Value | Confidence | Approval | Note |
|---|---|---|---|---|
| endpoint | TBD | UNKNOWN | UNAPPROVED | Do not browse or infer the endpoint. |
| namespace_indexes | TBD | UNKNOWN | UNAPPROVED | CODESYS OPC UA namespace table has not been inspected. |
| namespace_uris | TBD | UNKNOWN | UNAPPROVED | CODESYS OPC UA namespace table has not been inspected. |
| node_id_style | TBD | UNKNOWN | UNAPPROVED | Production identifier representation is unknown. |
| security_policy | TBD | UNKNOWN | UNAPPROVED | Non-local production OPC UA must use SignAndEncrypt; no final SecurityPolicy is selected here. |
| trusted_server_certificate_identity | TBD | UNKNOWN | UNAPPROVED | Trusted server identity has not been supplied. |
| authentication_method | TBD | UNKNOWN | UNAPPROVED | Production authentication method is unapproved. |
| dedicated_read_only_account | TBD | UNKNOWN | UNAPPROVED | Dedicated read-only account has not been provisioned. |
| source_timestamp_behavior | TBD | UNKNOWN | UNAPPROVED | PLC SourceTimestamp behavior must be verified during localhost/offline commissioning. |
| engineering_unit_metadata | TBD | UNKNOWN | UNAPPROVED | Availability and authority of OPC UA engineering-unit metadata is unknown. |

## Commissioning rules

- `STRONGLY_INFERRED` and `WEAKLY_INFERRED` are never production approval.
- Setpoint outputs `%QW27`, `%QW24`, and `%QW26` are command-side context only and must not be used as actual readbacks.
- The CFPS voltage-to-power relationship is unresolved and non-linear; no guessed W/V conversion is permitted.
- Raw versus converted IPPS symbols must be selected only after inspecting the CODESYS OPC UA Symbol Configuration and verifying the 750-471 process-image mode.
- Arc aggregation, polarity, latching, recovery, and severity remain unresolved.
