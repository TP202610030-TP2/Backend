from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.dependencies import get_current_user, get_http_client
from app.core.config import settings
from app.core.exceptions import GatewayTimeoutError, ServiceUnavailableError
from app.schemas import (
    LoginRequest,
    PasswordRecoveryRequest,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    error_responses,
)

router = APIRouter(tags=["auth"])


def _fwd(resp: httpx.Response) -> Response:
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


async def _post(http: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    try:
        return await http.post(url, **kwargs)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("upstream") from exc


@router.post(
    "/api/v1/auth/register",
    status_code=201,
    summary="Registrar una cuenta",
    description=(
        "Crea una cuenta nueva con correo, contraseña (8-128 caracteres) y nombre completo. "
        "Devuelve 400 con `VALIDATION_003` si el correo ya está registrado."
    ),
    response_model=RegisterResponse,
    responses=error_responses(400, 422, 502, 504),
)
async def register(
    body: RegisterRequest,
    http: httpx.AsyncClient = Depends(get_http_client),
):
    resp = await _post(
        http,
        f"{settings.user_service_url}/api/v1/auth/register",
        json=body.model_dump(mode="json"),
    )
    return _fwd(resp)


@router.post(
    "/api/v1/auth/login",
    summary="Iniciar sesión",
    description=(
        "Valida las credenciales y devuelve un JWT válido por 24 h. Tras 5 intentos fallidos "
        "en 15 minutos el correo queda bloqueado temporalmente (429)."
    ),
    response_model=TokenResponse,
    responses=error_responses(401, 403, 422, 429, 502, 504),
)
async def login(
    body: LoginRequest,
    http: httpx.AsyncClient = Depends(get_http_client),
):
    resp = await _post(
        http,
        f"{settings.auth_service_url}/api/v1/auth/login",
        json=body.model_dump(mode="json"),
    )
    return _fwd(resp)


@router.post(
    "/api/v1/auth/logout",
    status_code=204,
    summary="Cerrar sesión",
    description="Revoca el token JWT enviado en el header `Authorization`; deja de ser aceptado de inmediato.",
    responses=error_responses(401, 502, 504),
)
async def logout(
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    # Blocklist the token — expires_at set to now+24h as a safe upper bound
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    await _post(
        http,
        f"{settings.auth_service_url}/internal/auth/blocklist-token",
        json={"token": user["token"], "expires_at": expires_at},
    )


@router.post(
    "/api/v1/auth/password-recovery",
    status_code=204,
    summary="Solicitar recuperación de contraseña",
    description=(
        "Envía al correo indicado un enlace para restablecer la contraseña (válido 1 hora). "
        "Devuelve 404 con `RESOURCE_001` si no existe un usuario con ese correo y 503 si el "
        "correo no pudo enviarse."
    ),
    responses=error_responses(404, 422, 502, 503, 504),
)
async def password_recovery(
    body: PasswordRecoveryRequest,
    http: httpx.AsyncClient = Depends(get_http_client),
):
    # The auth-service status is forwarded as-is: previously this always
    # answered 204, hiding "user not found" and e-mail delivery failures.
    resp = await _post(
        http,
        f"{settings.auth_service_url}/api/v1/auth/password-recovery",
        json=body.model_dump(mode="json"),
    )
    return _fwd(resp)


@router.post(
    "/api/v1/auth/password-reset",
    status_code=204,
    summary="Restablecer contraseña",
    description="Establece una nueva contraseña usando el token recibido por correo. El token es de un solo uso.",
    responses=error_responses(400, 401, 422, 502, 504),
)
async def password_reset(
    body: PasswordResetRequest,
    http: httpx.AsyncClient = Depends(get_http_client),
):
    resp = await _post(
        http,
        f"{settings.auth_service_url}/api/v1/auth/password-reset",
        json=body.model_dump(mode="json"),
    )
    return _fwd(resp)
