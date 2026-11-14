"""Public request/response schemas of the API Gateway.

They mirror the downstream services' schemas so that Swagger (/api/docs)
documents every request body and response (CP040). Request models are also
validated at the edge; business rules (phone format, minimum age, duplicated
email, ...) remain in the owning service.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Errors ----------

class ErrorDetail(BaseModel):
    field: str = Field(..., description="Parámetro con problemas", examples=["file"])
    location: str = Field(..., description="Dónde se esperaba: body, query, path o header", examples=["body"])
    issue: str = Field(..., description="Descripción del problema", examples=["Field required"])


class ErrorResponse(BaseModel):
    status: str = Field("error", examples=["error"])
    errorCode: str = Field(..., description="Código de error estable de la plataforma", examples=["VALIDATION_001"])
    message: str = Field(..., description="Mensaje descriptivo", examples=["Missing required parameter(s): file"])
    details: Optional[list[ErrorDetail]] = Field(None, description="Detalle por parámetro (solo errores de validación)")
    requestId: Optional[str] = Field(None, description="Identificador para correlacionar con los logs del servidor")
    timestamp: datetime


def error_responses(*codes: int) -> dict:
    """``responses=`` entry for FastAPI routes documenting the error envelope."""
    descriptions = {
        400: "Solicitud inválida",
        401: "Token ausente, inválido o expirado",
        403: "Acceso denegado al recurso",
        404: "Recurso no encontrado",
        409: "Conflicto con el estado actual del recurso",
        413: "El archivo supera el tamaño máximo permitido (50 MB)",
        422: "Parámetros obligatorios faltantes o con formato inválido",
        429: "Demasiadas solicitudes",
        500: "Error interno del servidor (se registra en los logs con su requestId)",
        502: "Servicio interno no disponible",
        503: "Servicio saturado o no disponible, reintentar más tarde",
        504: "Tiempo de espera agotado en un servicio interno",
    }
    return {c: {"model": ErrorResponse, "description": descriptions.get(c, "Error")} for c in codes}


# ---------- Auth ----------

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., examples=["usuario@correo.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["Segura2025!"])
    full_name: str = Field(..., min_length=1, max_length=100, examples=["Inti Quispe"])


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["usuario@correo.com"])
    password: str = Field(..., min_length=1, examples=["Segura2025!"])


class UserInfo(BaseModel):
    user_id: str
    email: str
    full_name: str = ""


class TokenResponse(BaseModel):
    token: str = Field(..., description="JWT a enviar en el header Authorization: Bearer <token>")
    expires_in: int = Field(86400, description="Vigencia del token en segundos")
    user: UserInfo


class PasswordRecoveryRequest(BaseModel):
    email: EmailStr = Field(..., examples=["usuario@correo.com"])


class PasswordResetRequest(BaseModel):
    token: str = Field(..., description="Token recibido en el enlace del correo de recuperación")
    new_password: str = Field(..., min_length=8, max_length=128, examples=["NuevaClave2025!"])


# ---------- Users ----------

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100, examples=["Inti Quispe Mamani"])
    phone_number: Optional[str] = Field(
        None, description="Formato E.164", examples=["+51987654321"]
    )
    date_of_birth: Optional[date] = Field(
        None, description="AAAA-MM-DD; el usuario debe tener al menos 13 años", examples=["2000-05-17"]
    )


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    phone_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    created_at: datetime


# ---------- Transcriptions ----------

class WordConfidence(BaseModel):
    word: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    start_time: float
    end_time: float
    sequence_number: int = 0


class TranscriptionResponse(BaseModel):
    transcription_id: str
    user_id: str
    audio_id: str
    text: str
    audio_filename: str
    audio_duration: float = Field(..., description="Duración del audio en segundos")
    processing_time: float = Field(..., description="Tiempo de procesamiento en segundos")
    created_at: datetime
    confidence_scores: list[WordConfidence] = []
    device_used: str = "cpu"
    compute_type: str = "fp32"


class TranscriptionListItem(BaseModel):
    transcription_id: str
    text: str
    audio_filename: str
    audio_duration: float
    created_at: datetime


class PaginationMeta(BaseModel):
    current_page: int
    page_size: int
    total_pages: int
    total_items: int


class TranscriptionListResponse(BaseModel):
    transcriptions: list[TranscriptionListItem]
    pagination: PaginationMeta


class RenameTranscriptionRequest(BaseModel):
    audio_filename: str = Field(..., min_length=1, max_length=255, examples=["entrevista-cusco.wav"])


# ---------- Jobs ----------

class JobAcceptedResponse(BaseModel):
    job_id: str
    audio_id: str
    status: str = Field(..., examples=["queued"])
    status_url: str = Field(..., description="URL a consultar con GET para conocer el estado")
    queue_backlog: int = Field(0, description="Trabajos pendientes en la cola al momento de encolar")


class JobStatusResponse(BaseModel):
    job_id: str
    status: str = Field(..., description="queued | processing | completed | failed")

    model_config = {"extra": "allow"}
