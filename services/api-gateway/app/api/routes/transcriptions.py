import httpx
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.api.dependencies import get_current_user, get_http_client
from app.core.config import settings
from app.core.exceptions import GatewayTimeoutError, ServiceUnavailableError
from app.schemas import (
    RenameTranscriptionRequest,
    TranscriptionListResponse,
    TranscriptionResponse,
    error_responses,
)

router = APIRouter(tags=["transcriptions"])


_FORWARDED_HEADERS = {"content-disposition", "retry-after"}


def _fwd(resp: httpx.Response) -> Response:
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
        headers={
            k: v
            for k, v in resp.headers.items()
            if k.lower() in _FORWARDED_HEADERS
        },
    )


@router.post(
    "/api/v1/transcribe",
    summary="Transcribir un archivo de audio",
    description=(
        "Sube un audio en quechua como `multipart/form-data` (campo obligatorio `file`) y devuelve "
        "la transcripción con la confianza por palabra. Formatos: WAV, MP3, FLAC, OGG y M4A; "
        "tamaño máximo 50 MB. Si falta `file` responde 422 `VALIDATION_001` indicando el parámetro."
    ),
    response_model=TranscriptionResponse,
    responses=error_responses(400, 401, 413, 422, 502, 503, 504),
)
async def transcribe(
    file: UploadFile = File(..., description="Archivo de audio a transcribir"),
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        content = await file.read()
        resp = await http.post(
            f"{settings.audio_processor_url}/internal/audio/process",
            files={"file": (file.filename, content, file.content_type)},
            data={"user_id": user["user_id"]},
            timeout=settings.transcribe_timeout,
        )
        return _fwd(resp)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("audio-processor") from exc


@router.get(
    "/api/v1/transcriptions",
    summary="Listar mi historial de transcripciones",
    description="Devuelve las transcripciones del usuario, de la más reciente a la más antigua, paginadas.",
    response_model=TranscriptionListResponse,
    responses=error_responses(401, 422, 502, 504),
)
async def list_transcriptions(
    page: int = Query(1, ge=1, description="Número de página (desde 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página (1-100)"),
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        resp = await http.get(
            f"{settings.transcription_manager_url}/api/v1/transcriptions",
            params={"page": page, "page_size": page_size},
            headers={"X-User-Id": user["user_id"]},
        )
        return _fwd(resp)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("transcription-manager") from exc


@router.get(
    "/api/v1/transcriptions/{transcription_id}",
    summary="Obtener una transcripción",
    description="Devuelve el detalle de una transcripción propia, incluida la confianza por palabra.",
    response_model=TranscriptionResponse,
    responses=error_responses(401, 403, 404, 502, 504),
)
async def get_transcription(
    transcription_id: str,
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        resp = await http.get(
            f"{settings.transcription_manager_url}/api/v1/transcriptions/{transcription_id}",
            headers={"X-User-Id": user["user_id"]},
        )
        return _fwd(resp)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("transcription-manager") from exc


@router.patch(
    "/api/v1/transcriptions/{transcription_id}",
    summary="Renombrar una transcripción",
    description="Cambia el nombre mostrado en el historial y usado en las descargas.",
    response_model=TranscriptionResponse,
    responses=error_responses(401, 403, 404, 422, 502, 504),
)
async def rename_transcription(
    transcription_id: str,
    body: RenameTranscriptionRequest,
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        resp = await http.patch(
            f"{settings.transcription_manager_url}/api/v1/transcriptions/{transcription_id}",
            json=body.model_dump(mode="json"),
            headers={"X-User-Id": user["user_id"]},
        )
        return _fwd(resp)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("transcription-manager") from exc


@router.delete(
    "/api/v1/transcriptions/{transcription_id}",
    status_code=204,
    summary="Eliminar una transcripción",
    description="Elimina de forma permanente la transcripción y sus datos asociados (confianza por palabra).",
    responses=error_responses(401, 403, 404, 502, 504),
)
async def delete_transcription(
    transcription_id: str,
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        resp = await http.delete(
            f"{settings.transcription_manager_url}/api/v1/transcriptions/{transcription_id}",
            headers={"X-User-Id": user["user_id"]},
        )
        return _fwd(resp)
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("transcription-manager") from exc


@router.get(
    "/api/v1/transcriptions/{transcription_id}/download",
    summary="Descargar una transcripción",
    description="Descarga la transcripción como archivo en el formato indicado.",
    responses={
        200: {
            "description": "Archivo de la transcripción",
            "content": {"text/plain": {}, "application/json": {}, "application/x-subrip": {}},
        },
        **error_responses(400, 401, 403, 404, 422, 502, 504),
    },
)
async def download_transcription(
    transcription_id: str,
    format: str = Query(..., description="Formato del archivo: txt, json o srt", examples=["txt"]),
    http: httpx.AsyncClient = Depends(get_http_client),
    user: dict = Depends(get_current_user),
):
    try:
        resp = await http.get(
            f"{settings.transcription_manager_url}/api/v1/transcriptions/{transcription_id}/download",
            params={"format": format},
            headers={"X-User-Id": user["user_id"]},
        )
        headers = {}
        if "content-disposition" in resp.headers:
            headers["Content-Disposition"] = resp.headers["content-disposition"]
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type"),
            headers=headers,
        )
    except httpx.TimeoutException as exc:
        raise GatewayTimeoutError() from exc
    except httpx.ConnectError as exc:
        raise ServiceUnavailableError("transcription-manager") from exc
