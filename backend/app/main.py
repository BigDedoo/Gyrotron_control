from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import endpoints
from app.core.config import AppSettings, OPCUASettings, get_settings
from app.models import AppMode
from app.opcua.monitor import OPCUAMonitor
from app.opcua.node_map import NodeMap, load_node_map


MonitorFactory = Callable[[OPCUASettings, NodeMap], OPCUAMonitor]


def create_app(
    settings: AppSettings | None = None,
    *,
    monitor_factory: MonitorFactory = OPCUAMonitor,
) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        monitor: OPCUAMonitor | None = None
        if app_settings.app_mode == AppMode.OPCUA_READONLY:
            if app_settings.opcua is None:
                raise RuntimeError("OPC UA configuration is missing")
            node_map = load_node_map(app_settings.opcua.node_map_path)
            monitor = monitor_factory(app_settings.opcua, node_map)
            application.state.opcua_monitor = monitor
            await monitor.start()
        try:
            yield
        finally:
            if monitor is not None:
                await monitor.stop()
                application.state.opcua_monitor = None

    application = FastAPI(title="Gyrotron Control API", lifespan=lifespan)
    application.state.settings = app_settings
    application.state.opcua_monitor = None

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
