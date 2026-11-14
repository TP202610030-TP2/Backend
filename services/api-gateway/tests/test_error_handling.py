"""CP038 / CP044 / CP046: uniform, descriptive JSON errors from the gateway."""
import logging

import httpx
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.api.dependencies import get_current_user, get_http_client
from app.main import app


def _user():
    return {"user_id": "uid-1", "email": "user@example.com", "token": "tok"}


@pytest.fixture
def client():
    http = AsyncMock(spec=httpx.AsyncClient)
    app.dependency_overrides[get_http_client] = lambda: http
    app.dependency_overrides[get_current_user] = _user
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, http
    app.dependency_overrides.clear()


def _assert_envelope(body: dict, code: str):
    assert body["status"] == "error"
    assert body["errorCode"] == code
    assert body["message"]
    assert body["requestId"]
    assert body["timestamp"]


def test_transcribe_without_file_names_missing_parameter(client):
    c, http = client
    resp = c.post("/api/v1/transcribe", data={"other": "x"})
    assert resp.status_code == 422
    body = resp.json()
    _assert_envelope(body, "VALIDATION_001")
    assert "file" in body["message"]
    assert body["details"][0]["field"] == "file"
    http.post.assert_not_called()


@pytest.mark.parametrize(
    "content_type",
    ["multipart/form-data", "multipart/form-data; boundary=xyz"],
)
def test_transcribe_malformed_multipart_is_422_and_descriptive(client, content_type):
    """Previously: 400 "There was an error parsing the body" without naming `file`."""
    c, _ = client
    resp = c.post("/api/v1/transcribe", content=b"", headers={"content-type": content_type})
    assert resp.status_code == 422
    body = resp.json()
    _assert_envelope(body, "VALIDATION_001")
    assert "file" in body["message"]


def test_invalid_json_body_is_422_not_500(client):
    c, _ = client
    resp = c.post(
        "/api/v1/auth/login", content=b"{bad", headers={"content-type": "application/json"}
    )
    assert resp.status_code == 422
    _assert_envelope(resp.json(), "VALIDATION_001")


def test_login_missing_fields_lists_them(client):
    c, http = client
    resp = c.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422
    fields = {d["field"] for d in resp.json()["details"]}
    assert fields == {"email", "password"}
    http.post.assert_not_called()


def test_internal_error_returns_json_and_is_logged(client, caplog):
    c, http = client
    http.get.side_effect = RuntimeError("boom")
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        resp = c.get("/api/v1/users/profile")
    assert resp.status_code == 500
    body = resp.json()
    _assert_envelope(body, "SYSTEM_001")
    assert "boom" not in body["message"]  # internals are not leaked to the client
    assert resp.headers["X-Request-Id"] == body["requestId"]
    assert any(body["requestId"] in r.getMessage() for r in caplog.records)


def test_unknown_route_uses_error_envelope(client):
    c, _ = client
    resp = c.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "RESOURCE_001")


def test_openapi_documents_bodies_and_descriptions(client):
    c, _ = client
    spec = c.get("/api/openapi.json").json()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op.get("summary"), f"{method.upper()} {path} has no summary"
            if path.startswith("/api/"):
                assert op.get("description"), f"{method.upper()} {path} has no description"
    for path in (
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/password-recovery",
        "/api/v1/auth/password-reset",
    ):
        assert "requestBody" in spec["paths"][path]["post"], path
    assert "requestBody" in spec["paths"]["/api/v1/users/profile"]["put"]
    assert "ErrorResponse" in spec["components"]["schemas"]
