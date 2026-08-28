from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.commands.capabilities import CommandCapabilitiesResponse, phase4_capabilities
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
from app.events.models import EventCategory, EventCreate, EventListResponse
from app.events.store import EventStore, EventStoreUnavailable
from app.models import (
    AlarmSeverity,
    AppMode,
    DataState,
    LoginRequest,
    MessageResponse,
    SessionUser,
    SystemStatus,
    TelemetryPoint,
    UserCreateRequest,
    UserRecord,
    UserRemoveRequest,
    UserUpdateRequest,
    UsersResponse,
)
from app.simulation import simulation_telemetry


router = APIRouter(prefix="/api")


def _event_store(request: Request) -> EventStore | None:
    return getattr(request.app.state, "event_store", None)


def _record_event(request: Request, event: EventCreate) -> None:
    store = _event_store(request)
    if store is not None:
        store.append(event)


def _session_response(session: ApplicationSession) -> SessionUser:
    return SessionUser(
        username=session.username,
        role=session.role,
        expires_at=session.expires_at,
    )


@router.post("/login", response_model=SessionUser)
def login(credentials: LoginRequest, response: Response, request: Request) -> SessionUser:
    if not authenticate_user(credentials.username, credentials.password):
        _record_event(
            request,
            EventCreate(
                category=EventCategory.SECURITY,
                event_type="security.login_failed",
                source="authentication",
                actor=credentials.username,
                message="Login failed",
                details={"reason": "invalid_credentials"},
            ),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    role = user_manager.get_role(credentials.username)
    if role is None:
        _record_event(
            request,
            EventCreate(
                category=EventCategory.SECURITY,
                event_type="security.login_denied",
                source="authentication",
                actor=credentials.username,
                message="Login denied for unauthorized user",
                details={"reason": "user_not_authorized"},
            ),
        )
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
    _record_event(
        request,
        EventCreate(
            category=EventCategory.SECURITY,
            event_type="security.login_succeeded",
            source="authentication",
            actor=credentials.username,
            message="Login succeeded",
            details={"role": role.value},
        ),
    )
    return _session_response(session)


@router.get("/session", response_model=SessionUser)
def get_session(session: ApplicationSession = Depends(get_current_session)) -> SessionUser:
    return _session_response(session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: ApplicationSession = Depends(get_current_session),
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
    _record_event(
        request,
        EventCreate(
            category=EventCategory.SECURITY,
            event_type="security.logout",
            source="authentication",
            actor=session.username,
            message="User logged out",
        ),
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


def _apply_user_change(
    operation: Callable[[UserManager], None],
    *,
    request: Request,
    actor: ApplicationSession,
    event_type: str,
    target: str,
    details: dict[str, str] | None = None,
) -> UsersResponse:
    try:
        operation(user_manager)
    except (UserAlreadyExists, UserNotFound, LastAdministratorError, UserStorageError) as exc:
        raise _user_error(exc) from exc
    _record_event(
        request,
        EventCreate(
            category=EventCategory.OPERATOR,
            event_type=event_type,
            source="operator",
            actor=actor.username,
            target=target,
            message=f"User administration action completed for {target}",
            details=details or {},
        ),
    )
    return UsersResponse(users=user_manager.get_users())


@router.post("/users/add", response_model=UsersResponse, status_code=status.HTTP_201_CREATED)
def add_user(
    action: UserCreateRequest,
    request: Request,
    actor: ApplicationSession = Depends(require_admin),
) -> UsersResponse:
    return _apply_user_change(
        lambda manager: manager.add_user(action.username, action.role),
        request=request,
        actor=actor,
        event_type="operator.user_added",
        target=action.username,
        details={"role": action.role.value},
    )


@router.post("/users/update", response_model=UsersResponse)
def update_user(
    action: UserUpdateRequest,
    request: Request,
    actor: ApplicationSession = Depends(require_admin),
) -> UsersResponse:
    return _apply_user_change(
        lambda manager: manager.update_role(action.username, action.role),
        request=request,
        actor=actor,
        event_type="operator.user_role_changed",
        target=action.username,
        details={"role": action.role.value},
    )


@router.post("/users/remove", response_model=UsersResponse)
def remove_user(
    action: UserRemoveRequest,
    request: Request,
    actor: ApplicationSession = Depends(require_admin),
) -> UsersResponse:
    return _apply_user_change(
        lambda manager: manager.remove_user(action.username),
        request=request,
        actor=actor,
        event_type="operator.user_removed",
        target=action.username,
    )


@router.get("/events", response_model=EventListResponse)
def get_events(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None, gt=0),
    category: EventCategory | None = None,
    severity: AlarmSeverity | None = None,
    event_type: str | None = Query(default=None, min_length=1, max_length=128),
    actor: str | None = Query(default=None, min_length=1, max_length=128),
    _: ApplicationSession = Depends(get_current_session),
) -> EventListResponse:
    store = _event_store(request)
    if store is None or not store.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event history is unavailable",
        )
    try:
        events = store.query(
            limit=limit + 1,
            before_id=before_id,
            category=category,
            severity=severity,
            event_type=event_type,
            actor=actor,
        )
    except EventStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event history is unavailable",
        ) from exc
    has_more = len(events) > limit
    page = events[:limit]
    return EventListResponse(
        events=page,
        next_before_id=page[-1].id if has_more and page else None,
        store_available=True,
    )


@router.get("/command-capabilities", response_model=CommandCapabilitiesResponse)
def get_command_capabilities(
    _: ApplicationSession = Depends(get_current_session),
) -> CommandCapabilitiesResponse:
    return phase4_capabilities()


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
        return getattr(view.snapshot, "telemetry", view.snapshot)

    return simulation_telemetry(
        problem_cycle_seconds=settings.simulation_problem_cycle_seconds
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
    request: Request,
    actor: ApplicationSession = Depends(get_current_session),
) -> MessageResponse:
    _record_event(
        request,
        EventCreate(
            category=EventCategory.COMMAND,
            event_type="command.rejected",
            source="operator",
            actor=actor.username,
            target="setpoint.apply",
            message="Setpoint command rejected because hardware command execution is unavailable",
            details={"reason": "hardware_command_execution_unavailable"},
        ),
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Hardware setpoint commands are unavailable in this read-only application",
    )
