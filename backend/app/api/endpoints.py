import math
import time
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.auth import authenticate_user
from app.core.config import get_settings
from app.core.sessions import (
    ApplicationSession,
    get_current_session,
    require_admin,
    session_manager,
)
from app.core.system_status import get_system_status
from app.core.users import (
    LastAdministratorError,
    UserAlreadyExists,
    UserManager,
    UserNotFound,
    UserStorageError,
    user_manager,
)
from app.models import (
    AppMode,
    DataSource,
    DataState,
    LoginRequest,
    MessageResponse,
    SessionUser,
    SignalQuality,
    SignalValue,
    SystemStatus,
    TelemetryPoint,
    UserCreateRequest,
    UserRecord,
    UserRemoveRequest,
    UserUpdateRequest,
    UsersResponse,
)


router = APIRouter(prefix="/api")
start_time = time.monotonic()


def _session_response(session: ApplicationSession) -> SessionUser:
    return SessionUser(
        username=session.username,
        role=session.role,
        expires_at=session.expires_at,
    )


@router.post("/login", response_model=SessionUser)
def login(credentials: LoginRequest, response: Response, request: Request) -> SessionUser:
    if not authenticate_user(credentials.username, credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    role = user_manager.get_role(credentials.username)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not authorized")

    settings = getattr(request.app.state, "settings", get_settings())
    session = session_manager.create(credentials.username, role)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session.token,
        max_age=settings.session_ttl_seconds,
        expires=session.expires_at,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return _session_response(session)


@router.get("/session", response_model=SessionUser)
def get_session(session: ApplicationSession = Depends(get_current_session)) -> SessionUser:
    return _session_response(session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    _: ApplicationSession = Depends(get_current_session),
) -> Response:
    settings = getattr(request.app.state, "settings", get_settings())
    session_manager.destroy(request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/users", response_model=list[UserRecord])
def get_users(_: ApplicationSession = Depends(require_admin)) -> list[UserRecord]:
    return user_manager.get_users()


def _user_error(exc: Exception) -> HTTPException:
    if isinstance(exc, UserAlreadyExists):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, UserNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, LastAdministratorError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="User store operation failed",
    )


def _apply_user_change(operation: Callable[[UserManager], None]) -> UsersResponse:
    try:
        operation(user_manager)
    except (UserAlreadyExists, UserNotFound, LastAdministratorError, UserStorageError) as exc:
        raise _user_error(exc) from exc
    return UsersResponse(users=user_manager.get_users())


@router.post("/users/add", response_model=UsersResponse, status_code=status.HTTP_201_CREATED)
def add_user(
    action: UserCreateRequest,
    _: ApplicationSession = Depends(require_admin),
) -> UsersResponse:
    return _apply_user_change(lambda manager: manager.add_user(action.username, action.role))


@router.post("/users/update", response_model=UsersResponse)
def update_user(
    action: UserUpdateRequest,
    _: ApplicationSession = Depends(require_admin),
) -> UsersResponse:
    return _apply_user_change(lambda manager: manager.update_role(action.username, action.role))


@router.post("/users/remove", response_model=UsersResponse)
def remove_user(
    action: UserRemoveRequest,
    _: ApplicationSession = Depends(require_admin),
) -> UsersResponse:
    return _apply_user_change(lambda manager: manager.remove_user(action.username))


@router.get("/telemetry", response_model=TelemetryPoint)
async def get_telemetry(
    request: Request,
    _: ApplicationSession = Depends(get_current_session),
) -> TelemetryPoint:
    settings = getattr(request.app.state, "settings", get_settings())
    if settings.app_mode == AppMode.OPCUA_READONLY:
        monitor = getattr(request.app.state, "opcua_monitor", None)
        if monitor is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPC UA telemetry monitor is unavailable",
            )
        view = monitor.view()
        if view.snapshot is None or view.data_state in {DataState.STALE, DataState.UNAVAILABLE}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OPC UA telemetry is {view.data_state.value}",
            )
        return view.snapshot

    elapsed = time.monotonic() - start_time
    sequence = int(elapsed)
    timestamp = datetime.now(timezone.utc)

    def sample(value: float, unit: str) -> SignalValue:
        return SignalValue(
            value=value,
            unit=unit,
            quality=SignalQuality.GOOD,
            source_timestamp=timestamp,
        )

    return TelemetryPoint(
        timestamp=timestamp,
        source=DataSource.SIMULATION,
        sequence=sequence,
        ionV=sample(4.5 + math.sin((elapsed / 6) * math.pi) * 0.6, "V"),
        ionI=sample(1.8 + math.cos((elapsed / 8) * math.pi) * 0.4, "A"),
        heatV=sample(7.0 + math.sin((elapsed / 5) * math.pi) * 0.8, "V"),
        heatI=sample(3.2 + math.cos((elapsed / 7) * math.pi) * 0.5, "A"),
        heLvl=sample(68 + math.sin((elapsed / 10) * math.pi) * 6, "%"),
        Thot=sample(62 + math.sin((elapsed / 9) * math.pi) * 3, "degC"),
        Tcold=sample(28 + math.cos((elapsed / 9) * math.pi) * 3, "degC"),
    )


@router.get("/status", response_model=SystemStatus)
async def system_status(
    request: Request,
    _: ApplicationSession = Depends(get_current_session),
) -> SystemStatus:
    settings = getattr(request.app.state, "settings", get_settings())
    monitor = getattr(request.app.state, "opcua_monitor", None)
    return get_system_status(settings, monitor)


@router.post("/setpoint", response_model=MessageResponse)
async def set_parameters(
    _: ApplicationSession = Depends(get_current_session),
) -> MessageResponse:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Hardware setpoint commands are unavailable in this read-only application",
    )
