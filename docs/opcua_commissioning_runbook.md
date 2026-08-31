# OPC UA commissioning harness runbook

This harness prepares and rehearses the Gyrotron Control read-only telemetry path. It does not discover a PLC, infer production NodeIds, or provide any write operation. All simulator traffic binds to `127.0.0.1`.

## Phase A — offline and localhost

1. Obtain a read-only UaExpert, Prosys, or equivalent browse record from an explicitly approved workstation. There is no tested proprietary-export adapter yet.
2. Normalize the browse evidence into the canonical JSON format below. Copy values exactly; do not derive NodeIds from symbol paths or BrowseNames.
3. Reconcile exact exported CODESYS symbol paths:

   ```powershell
   cd backend
   python -m app.opcua.harness reconcile --commissioning-template config/opcua_nodes.production.template.json --discovered-nodes tests/commissioning/fixtures/discovered-full-good.json --output reconciliation.md
   ```

4. Review every `MISSING`, `AMBIGUOUS`, `DATATYPE_MISMATCH`, `ACCESS_WARNING`, and `UNIT_WARNING`. Fuzzy BrowseName matches are never accepted automatically.
5. Generate a guarded draft:

   ```powershell
   python -m app.opcua.harness generate-draft --commissioning-template config/opcua_nodes.production.template.json --discovered-nodes discovered_nodes.json --output draft-production-map.json
   ```

   The result has `purpose=draft-production`, `approved=false`, and evidence-only fields which the strict runtime schema rejects. It cannot be promoted by changing one metadata value. A human must independently author and review a strict production `NodeMap`.

6. Rehearse software behavior against localhost using a test map and scenario fixture:

   ```powershell
   python -m app.opcua.harness simulator --fixture tests/commissioning/fixtures/full-good.json
   python -m app.opcua.harness rehearse --map path/to/localhost-test-map.json
   ```

7. Exercise normal, uncertain/bad quality, stale timestamps, missing nodes, wrong datatypes, disconnect/reconnect, partial mapping, changing values, and non-finite numeric scenarios. Check the existing Diagnostics page under **OPC UA commissioning**. It labels normal simulation, localhost testing, and production OPC UA distinctly.
8. Archive the canonical input, reconciliation report, reviewed mapping evidence, test output, and approval record.

### Canonical discovered-node JSON

The root fields are `schema_version: 1`, `source_format: "canonical-json"`, `captured_offline: true`, and `nodes`. Every node requires:

- `symbol_path`, `node_id`, `namespace_uri`, and `namespace_index`
- `browse_name` and `display_name`
- `data_type`
- `access_level` and effective `user_access_level`
- nullable `engineering_unit`
- nullable boolean `source_timestamp_observed`

See `backend/tests/commissioning/fixtures/discovered-full-good.json` for a synthetic TestOnly example. Future proprietary-format adapters should only normalize into this model; matching and draft logic remain format-independent.

Telemetry should be effectively readable by the application identity and should not need effective write access. Access is verified from metadata only—never by performing a write.

## Phase B — real PFC200 read-only (separately authorized)

1. Install approved client and server certificates and verify the server-certificate identity.
2. Configure only the approved endpoint and SecurityPolicy.
3. Use the approved dedicated read-only application identity.
4. Start with a very small, human-approved subset.
5. Compare the same values, types, units, quality, and timestamps in CODESYS, the browse client, FastAPI diagnostics, and the HMI.
6. Expand the mapping gradually after each subset is accepted.
7. Validate disconnection and automatic recovery without changing PLC state.
8. Archive final commissioning evidence and approvals.

**NO WRITE TESTS ARE REQUIRED OR ALLOWED FOR THIS READ-ONLY COMMISSIONING PHASE.**

The following remain hardware/controls decisions, not harness results: the 750-471 WORD process representation, PoorVacuum polarity, CFPS stabilization polarity and final feedback-field approval, Arc Detector selection/aggregation/latching/recovery/severity, and approved IPPS operating ranges. The eight fields with no physical source remain excluded: `cmps.current`, `cfps.power`, `ahvps.voltage`, `chvps.voltage`, and the four pulse-generator fields.
