"""Uniform JSON error responses for every error raised by the gateway itself.

Before this module the gateway only registered a handler for ``Exception``.
Starlette resolves handlers by MRO, so ``HTTPException`` and
``RequestValidationError`` kept FastAPI's defaults: raw ``{"detail": ...}``
bodies and, for a malformed multipart upload, a bare
``400 "There was an error parsing the body"`` that does not say which
parameter is missing (CP038). Unhandled exceptions were also answered without
being logged (CP046).

Every error now uses the envelope documented in Swagger (``ErrorResponse``)::

    {"status": "error", "errorCode": "...", "message": "...",
     "details": [...], "requestId": "...", "timestamp": "..."}

Errors forwarded verbatim from downstream services are not touched.
"""
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

from app.core.response import error_response

logger = logging.getLogger("app.errors")

# Messages FastAPI/Starlette use when the request body cannot be parsed at all.
_BODY_PARSE_MARKERS = (
    "error parsing the body",
    "missing boundary",
    "json decode error",
)

_STATUS_TO_CODE = {
    400: "VALIDATION_001",
    401: "AUTH_001",
    403: "AUTH_002",
    404: "RESOURCE_001",
    405: "SYSTEM_005",
    413: "VALIDATION_002",
    422: "VALIDATION_001",
    429: "SYSTEM_003",
    502: "SYSTEM_002",
    503: "SYSTEM_003",
    504: "SYSTEM_004",
}


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or uuid.uuid4().hex


def _matching_route(request: Request):
    # FastAPI stores the matched APIRoute in the scope before parsing the body.
    route = request.scope.get("route")
    if route is not None:
        return route
    for candidate in request.app.router.routes:
        match, _ = candidate.matches(request.scope)
        if match == Match.FULL:
            return candidate
    return None


def _required_body_fields(request: Request) -> list[str]:
    """Names of the required body/form fields of the route matching *request*."""
    dependant = getattr(_matching_route(request), "dependant", None)
    if dependant is None:
        return []
    names = []
    for param in dependant.body_params:
        required = getattr(param, "required", None)
        field_info = getattr(param, "field_info", None)
        if required is None and field_info is not None:
            required = field_info.is_required()
        if required:
            names.append(getattr(param, "alias", None) or param.name)
    return names


def _field_path(loc: tuple | list) -> str:
    # ("body", "file") -> "file"; ("query", "page") -> "page"
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(parts) or ".".join(str(p) for p in loc)


def _validation_details(errors: list[dict]) -> list[dict]:
    details = []
    for err in errors:
        loc = err.get("loc", ())
        details.append(
            {
                "field": _field_path(loc),
                "location": str(loc[0]) if loc else "body",
                "issue": err.get("msg", "Invalid value"),
            }
        )
    return details


def _validation_message(details: list[dict]) -> str:
    missing = [d["field"] for d in details if d["issue"].lower() == "field required"]
    if missing and len(missing) == len(details):
        return "Missing required parameter(s): " + ", ".join(missing)
    return "Invalid request parameters: " + "; ".join(
        f"{d['field']}: {d['issue']}" for d in details
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _request_id(request)
    detail = exc.detail
    headers = getattr(exc, "headers", None)

    if isinstance(detail, dict):
        return error_response(
            detail.get("errorCode", _STATUS_TO_CODE.get(exc.status_code, "SYSTEM_001")),
            detail.get("message", "Request failed"),
            exc.status_code,
            headers=headers,
            request_id=request_id,
        )

    message = str(detail)
    if exc.status_code == 400 and any(m in message.lower() for m in _BODY_PARSE_MARKERS):
        # The body could not even be parsed (e.g. multipart without the file
        # part, or invalid JSON). Answer like any other validation error and
        # name the parameters the endpoint requires.
        fields = _required_body_fields(request)
        details = [
            {"field": f, "location": "body", "issue": "Field required"} for f in fields
        ]
        content_type = request.headers.get("content-type", "").split(";")[0] or "none"
        msg = "Malformed or incomplete request body (Content-Type: %s)." % content_type
        if fields:
            msg += " Missing required parameter(s): " + ", ".join(fields)
        return error_response("VALIDATION_001", msg, 422, details=details, request_id=request_id)

    if exc.status_code in (401, 403) and message == "Not authenticated":
        message = "Missing or invalid Authorization header (expected: Bearer <token>)"
    return error_response(
        _STATUS_TO_CODE.get(exc.status_code, "SYSTEM_001"),
        message,
        exc.status_code,
        headers=headers,
        request_id=request_id,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _request_id(request)
    errors = list(exc.errors())
    # Invalid JSON body arrives as a validation error of type "json_invalid".
    if any(e.get("type") == "json_invalid" for e in errors):
        return error_response(
            "VALIDATION_001", "Request body is not valid JSON", 422, request_id=request_id
        )
    details = _validation_details(errors)
    return error_response(
        "VALIDATION_001", _validation_message(details), 422, details=details, request_id=request_id
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    # CP046: every internal failure is written to the service log (stdout ->
    # Azure Log Analytics) with its traceback and a requestId that is also
    # returned to the client, so the two can be correlated.
    logger.error(
        "Unhandled error requestId=%s method=%s path=%s: %s",
        request_id,
        request.method,
        request.url.path,
        exc,
        exc_info=exc,
    )
    return error_response(
        "SYSTEM_001", "An unexpected internal error occurred", 500, request_id=request_id
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
