import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.dependencies import get_current_user, get_http_client
from app.core.config import settings
from app.schemas import error_responses

router = APIRouter(tags=["dashboard"])

_DASHBOARD_TIMEOUT = 0.5  # 500 ms
# The status-only endpoint is polled by the frontend while a service is still
# waking up (ACA scale-to-zero), so it can afford a longer per-service budget.
_STATUS_TIMEOUT = 2.0


async def _safe_get(http: httpx.AsyncClient, url: str, **kwargs) -> dict | None:
    try:
        resp = await asyncio.wait_for(
            http.get(url, **kwargs), timeout=_DASHBOARD_TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


async def _health(http: httpx.AsyncClient, url: str, timeout: float = _DASHBOARD_TIMEOUT) -> str:
    try:
        resp = await asyncio.wait_for(http.get(f"{url}/health"), timeout=timeout)
        if resp.status_code == 200:
            return resp.json().get("status", "unknown")
    except Exception:
        pass
    return "unavailable"


@router.get(
    "/api/v1/dashboard",
    summary="Panel principal",
    description=(
        "Resumen para el panel del usuario: datos del perfil, total de transcripciones y estado "
        "de los servicios. Si algún servicio no responde en 500 ms se muestra como `unavailable`."
    ),
    responses=error_responses(401),
)
async def dashboard(
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]

    profile_task = asyncio.create_task(
        _safe_get(http, f"{settings.user_service_url}/internal/users/{user_id}")
    )
    summary_task = asyncio.create_task(
        _safe_get(
            http,
            f"{settings.transcription_manager_url}/internal/transcriptions/summary",
            headers={"X-User-Id": user_id},
        )
    )
    auth_health_task = asyncio.create_task(_health(http, settings.auth_service_url))
    audio_health_task = asyncio.create_task(_health(http, settings.audio_processor_url))
    asr_health_task = asyncio.create_task(_health(http, settings.asr_service_url))
    trans_health_task = asyncio.create_task(_health(http, settings.transcription_manager_url))

    (
        profile,
        summary,
        auth_health,
        audio_health,
        asr_health,
        trans_health,
    ) = await asyncio.gather(
        profile_task,
        summary_task,
        auth_health_task,
        audio_health_task,
        asr_health_task,
        trans_health_task,
    )

    return JSONResponse(
        content={
            "status": "success",
            "data": {
                "user": profile or {"user_id": user_id, "email": user["email"]},
                "transcription_summary": summary or {"total": 0, "latest_at": None},
                "services": {
                    "auth": auth_health,
                    "audio-processor": audio_health,
                    "asr": asr_health,
                    "transcription-manager": trans_health,
                },
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


async def _services_status(http: httpx.AsyncClient, timeout: float) -> dict:
    names_urls = {
        "auth": settings.auth_service_url,
        "audio-processor": settings.audio_processor_url,
        "asr": settings.asr_service_url,
        "transcription-manager": settings.transcription_manager_url,
    }
    results = await asyncio.gather(*(_health(http, url, timeout) for url in names_urls.values()))
    return dict(zip(names_urls, results))


@router.get(
    "/api/v1/dashboard/services",
    summary="Estado de los servicios",
    description=(
        "Consulta solo el estado de los servicios internos (`healthy` o `unavailable`). "
        "Es más liviano que `/api/v1/dashboard` y el panel lo vuelve a consultar mientras "
        "algún servicio se está iniciando."
    ),
    responses=error_responses(401),
)
async def services_status(
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    return JSONResponse(
        content={
            "status": "success",
            "data": {"services": await _services_status(http, _STATUS_TIMEOUT)},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
