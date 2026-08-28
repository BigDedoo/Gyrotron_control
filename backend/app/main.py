import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import endpoints
from app.core.config import AppSettings, OPCUASettings, get_settings
from app.events.detector import EventTransitionDetector, observe_monitor_events
from app.events.models import EventCategory, EventCreate
from app.events.store import EventStore
from app.models import AppMode
from app.opcua.monitor import OPCUAMonitor
from app.opcua.node_map import NodeMap, load_node_map
from app.simulation import seed_simulation_events


MonitorFactory = Callable[[OPCUASettings, NodeMap], OPCUAMonitor]
EventStoreFactory = Callable[..., EventStore]


def create_app(
    settings: AppSettings | None = None,
    *,
    monitor_factory: MonitorFactory = OPCUAMonitor,
    event_store_factory: EventStoreFactory = EventStore,
) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        event_store = event_store_factory(app_settings.event_db_path)
        application.state.event_store = event_store
        event_store.append(
            EventCreate(
                category=EventCategory.APPLICATION,
                event_type="application.started",
                source="application",
                message="Gyrotron monitoring backend started",
                details={"mode": app_settings.app_mode.value},
            )
        )
        monitor: OPCUAMonitor | None = None
        event_observer_task: asyncio.Task[None] | None = None
        event_observer_stop = asyncio.Event()
        if app_settings.app_mode == AppMode.SIMULATION:
            seed_simulation_events(event_store)
        else:
            if app_settings.opcua is None:
                raise RuntimeError("OPC UA configuration is missing")
            node_map = load_node_map(app_settings.opcua.node_map_path)
            monitor = monitor_factory(app_settings.opcua, node_map)
            application.state.opcua_monitor = monitor
            await monitor.start()
        detector = EventTransitionDetector(event_store)
        event_observer_task = asyncio.create_task(
            observe_monitor_events(
                app_settings,
                monitor,
                detector,
                event_observer_stop,
            ),
            name="event-transition-observer",
        )
        try:
            yield
        finally:
            event_store.append(
                EventCreate(
                    category=EventCategory.APPLICATION,
                    event_type="application.stopping",
                    source="application",
                    message="Gyrotron monitoring backend shutting down",
                    details={"mode": app_settings.app_mode.value},
                )
            )
            event_observer_stop.set()
            if event_observer_task is not None:
                await event_observer_task
            if monitor is not None:
                await monitor.stop()
                application.state.opcua_monitor = None
            application.state.event_store = None

    application = FastAPI(title="Gyrotron Control API", lifespan=lifespan)
    application.state.settings = app_settings
    application.state.opcua_monitor = None
    application.state.event_store = None

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(endpoints.router)

    @application.get("/")
    async def root():
        return {"message": "Gyrotron Control System API Running"}

    return application


app = create_app()
