import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.dependencies import get_current_user, get_http_client
from app.core.config import settings
from app.core.exceptions import GatewayTimeoutError, ServiceUnavailableError
from app.schemas import UpdateProfileRequest, UserProfileResponse, error_responses

router = APIRouter(tags=["users"])


def _fwd(resp: httpx.Response) -> Response:
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


@router.get(
    "/api/v1/users/profile",
    summary="Obtener mi perfil",
    description="Devuelve los datos del usuario autenticado.",
    response_model=UserProfileResponse,
    responses=error_responses(401, 404, 502, 504),
)
async def get_profile(
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        resp = await http.get(
            f"{settings.user_service_url}/api/v1/users/profile",
            headers={"X-User-Id": user["user_id"]},
        )
        return _fwd(resp)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("user-service") from exc


@router.put(
    "/api/v1/users/profile",
    summary="Actualizar mi perfil",
    description=(
        "Actualiza solo los campos enviados (nombre, teléfono en formato E.164 y fecha de "
        "nacimiento; edad mínima 13 años). El correo no se modifica por este endpoint."
    ),
    response_model=UserProfileResponse,
    responses=error_responses(401, 404, 422, 502, 504),
)
async def update_profile(
    body: UpdateProfileRequest,
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        resp = await http.put(
            f"{settings.user_service_url}/api/v1/users/profile",
            # exclude_unset keeps "field omitted" distinct from "field: null"
            json=body.model_dump(mode="json", exclude_unset=True),
            headers={"X-User-Id": user["user_id"]},
        )
        return _fwd(resp)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("user-service") from exc
