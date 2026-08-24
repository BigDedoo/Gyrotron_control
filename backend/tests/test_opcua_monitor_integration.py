import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models import ConnectionState, DataState
from app.opcua.monitor import OPCUAMonitor
from tests.opcua_simulator import LocalOPCUASimulator, make_opcua_settings


async def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        await asyncio.sleep(0.02)


def test_monitor_reconnects_and_recovers_after_server_restart():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        node_map = simulator.node_map()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        monitor = OPCUAMonitor(settings, node_map)
        replacement: LocalOPCUASimulator | None = None
        await monitor.start()
        try:
            await _wait_until(
                lambda: monitor.view().connection_state == ConnectionState.CONNECTED
                and monitor.view().data_state == DataState.LIVE
            )
            first_sequence = monitor.view().snapshot.sequence

            await simulator.crash()
            await _wait_until(
                lambda: monitor.view().connection_state
                in {ConnectionState.DISCONNECTED, ConnectionState.ERROR}
            )
            assert monitor.view().data_state in {DataState.STALE, DataState.UNAVAILABLE}

            replacement = LocalOPCUASimulator(port=simulator.port)
            await replacement.start()
            await _wait_until(
                lambda: monitor.view().connection_state == ConnectionState.CONNECTED
                and monitor.view().snapshot is not None
                and monitor.view().snapshot.sequence > first_sequence
            )
            assert monitor.view().data_state == DataState.LIVE
        finally:
            await monitor.stop()
            await simulator.stop()
            if replacement is not None:
                await replacement.stop()

        assert not monitor.running
        assert monitor.view().connection_state == ConnectionState.DISCONNECTED

    asyncio.run(scenario())


def test_monitor_reports_unavailable_when_server_is_down_at_startup():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        node_map = simulator.node_map()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        await simulator.stop()

        monitor = OPCUAMonitor(settings, node_map)
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().connection_state == ConnectionState.ERROR)
            view = monitor.view()
            assert view.data_state == DataState.UNAVAILABLE
            assert view.snapshot is None
            assert view.error == "OPC UA connection failed"
        finally:
            await monitor.stop()

    asyncio.run(scenario())


def test_monitor_never_marks_an_old_or_previous_connection_snapshot_live():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        monitor = OPCUAMonitor(settings, simulator.node_map())
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
        finally:
            await monitor.stop()
            await simulator.stop()

        now = datetime.now(timezone.utc)
        monitor._connection_state = ConnectionState.CONNECTED
        monitor._last_successful_read = now - timedelta(
            seconds=settings.monitor_interval_seconds * 3
        )
        monitor._last_connection_attempt = now - timedelta(seconds=1)
        assert monitor.view().data_state == DataState.STALE

        monitor._last_successful_read = now - timedelta(
            seconds=settings.stale_after_seconds + 0.1
        )
        assert monitor.view().data_state == DataState.UNAVAILABLE

        monitor._last_successful_read = now
        monitor._last_connection_attempt = now + timedelta(milliseconds=1)
        assert monitor.view().data_state == DataState.STALE

    asyncio.run(scenario())
