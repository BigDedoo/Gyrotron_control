from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.opcua.commissioning import (
    CommissioningTemplateError,
    load_commissioning_template,
    render_nodeid_discovery_plan,
)
from app.opcua.node_map import NodeMapError, load_node_map
from app.opcua.reconciliation import (
    DiscoveredNodeError,
    generate_draft_map,
    reconcile_files,
    render_reconciliation_report,
    write_json,
)


async def _serve_localhost(args: argparse.Namespace) -> None:
    # The asyncua import stays outside every offline command path by design.
    from app.opcua.simulator import (
        LocalOPCUASimulator,
        SimulatorScenario,
        load_simulator_fixture,
    )

    fixture = load_simulator_fixture(args.fixture) if args.fixture else None
    scenario = fixture.scenario if fixture else SimulatorScenario(args.scenario)
    simulator = LocalOPCUASimulator.commissioning(
        scenario,
        target=args.target,
        port=args.port,
        fixture=fixture,
    )
    await simulator.start()
    print(f"LOCAL OPC UA TEST listening on {simulator.endpoint_url}")
    print("Read-only commissioning simulator; press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    finally:
        await simulator.stop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline/localhost OPC UA commissioning harness")
    commands = parser.add_subparsers(dest="action", required=True)

    simulator = commands.add_parser("simulator", help="run the loopback-only test server")
    simulator.add_argument(
        "--scenario",
        default="normal",
        choices=(
            "normal",
            "degraded-quality",
            "bad-quality",
            "stale",
            "missing-node",
            "wrong-type",
            "disconnect-reconnect",
            "partial-good",
            "value-changes",
            "invalid-numeric",
        ),
    )
    simulator.add_argument("--target")
    simulator.add_argument("--fixture", type=Path)
    simulator.add_argument("--port", type=int)

    reconcile = commands.add_parser("reconcile", help="reconcile canonical JSON offline")
    reconcile.add_argument("--commissioning-template", required=True, type=Path)
    reconcile.add_argument("--discovered-nodes", "--input", required=True, type=Path)
    reconcile.add_argument("--output", type=Path)

    draft = commands.add_parser("generate-draft", help="generate a guarded non-runtime draft")
    draft.add_argument("--commissioning-template", required=True, type=Path)
    draft.add_argument("--discovered-nodes", "--input", required=True, type=Path)
    draft.add_argument("--output", required=True, type=Path)

    report = commands.add_parser("report", help="render the offline NodeId discovery plan")
    report.add_argument("--commissioning-template", required=True, type=Path)

    rehearse = commands.add_parser("rehearse", help="validate a localhost test map offline")
    rehearse.add_argument("--map", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "simulator":
            asyncio.run(_serve_localhost(args))
            return 0
        if args.action == "report":
            template = load_commissioning_template(args.commissioning_template)
            print(render_nodeid_discovery_plan(template))
            return 0
        if args.action == "rehearse":
            node_map = load_node_map(args.map, allowed_purposes=frozenset({"test"}))
            print(
                f"Offline map rehearsal passed: {len(node_map.signals)} numeric and "
                f"{len(node_map.state_signals)} state mappings."
            )
            return 0
        result = reconcile_files(args.commissioning_template, args.discovered_nodes)
        if args.action == "reconcile":
            report_text = render_reconciliation_report(result)
            if args.output:
                args.output.write_text(report_text + "\n", encoding="utf-8")
            else:
                print(report_text)
            return 0
        write_json(args.output, generate_draft_map(result))
        print(f"Non-runnable draft written to {args.output}")
        return 0
    except (CommissioningTemplateError, DiscoveredNodeError, NodeMapError, OSError, ValueError) as exc:
        print(exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
