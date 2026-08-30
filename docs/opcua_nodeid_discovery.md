# Offline OPC UA NodeId discovery plan

> This checklist is generated only from committed commissioning metadata. It makes no network calls, opens no socket, instantiates no OPC UA client, and contains no inferred NodeIds.

Preferred exported fields awaiting read-only discovery: **15**

| HMI field | Preferred exported CODESYS path | Expected datatype | Symbol config access | HMI unit | Remaining verification |
|---|---|---|---|---|---|
| cmps.state | Application.GVL_IntS.gIntS_Inp.CMPS_On | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| interlock.cmps | Application.GVL_IntS.gIntS_Outp.Auth_CMPS | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| cfps.state | Application.GVL_IntS.gIntS_Inp.CFPS_On | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| cfps.feedback | Application.PLC_PRG.filamentData.Sts_Run | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY, NEEDS_CONTROLS_APPROVAL_FOR_FIELD_SELECTION |
| interlock.cfps | Application.GVL_IntS.gIntS_Outp.Auth_CFPS | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| ipps.state | Application.GVL_IntS.gIntS_Inp.IPPS_On | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| ipps.voltage | Application.PLC_PRG.daqData.IonPumpVoltage_kV | REAL | Read | V | NEEDS_NODE_ID_DISCOVERY, NEEDS_RANGE_APPROVAL, NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION |
| ipps.current | Application.PLC_PRG.daqData.IonPumpCurrent_mA | REAL | Read | A | NEEDS_NODE_ID_DISCOVERY, NEEDS_RANGE_APPROVAL, NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION |
| interlock.ipps | Application.GVL_IntS.gIntS_Outp.Auth_IPPS | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| ahvps.state | Application.GVL_IntS.gIntS_Inp.APS_On | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| ahvps.protection | Application.GVL_Alarms.gAlarms.ApsFault | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| interlock.ahvps | Application.GVL_IntS.gIntS_Outp.Auth_APS | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| chvps.state | Application.GVL_IntS.gIntS_Inp.CPS_On | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| chvps.protection | Application.GVL_Alarms.gAlarms.CpsFault | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |
| interlock.chvps | Application.GVL_IntS.gIntS_Outp.Auth_CPS | BOOL | Read | NOT APPLICABLE | NEEDS_NODE_ID_DISCOVERY |

## Operator record for the later live browse

For each row, record the Namespace URI, namespace index, exact NodeId, BrowseName, DataType, AccessLevel, UserAccessLevel, SourceTimestamp behavior, and engineering-unit metadata when present.

The generated Symbol Configuration exposes command and setpoint symbols as `ReadWrite`. During the later browse, verify that the production application identity has effective `UserAccessLevel` read-only for telemetry and no write permission to command/setpoint symbols. Do not attempt writes as a test.

Do not derive NodeIds from the exported paths. Record only exact values returned by the real server during the separately authorized read-only browse.
