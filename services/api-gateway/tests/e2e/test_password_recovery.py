"""
11.3 E2E: Password recovery (E1-HU04)

Covers:
- Request recovery → 204; unknown email → 404 forwarded from auth-service (CP008)
- Use valid recovery token → password updated (204)
- Use expired/used token → 400
"""
from .conftest import mock_resp


def test_request_recovery_known_email_returns_204(anon_client):
    """POST /api/v1/auth/password-recovery with registered email → 204."""
    c, http = anon_client
    http.post.return_value = mock_resp({}, status=204)

    resp = c.post(
        "/api/v1/auth/password-recovery",
        json={"email": "inti@quechua.org"},
    )

    assert resp.status_code == 204


def test_request_recovery_unknown_email_returns_404(anon_client):
    """Unknown email → auth-service 404 is forwarded so the UI can say so (CP008)."""
    c, http = anon_client
    http.post.return_value = mock_resp(
        {"detail": {"errorCode": "RESOURCE_001", "message": "No user is registered with this email"}},
        status=404,
    )

    resp = c.post(
        "/api/v1/auth/password-recovery",
        json={"email": "nobody@nowhere.com"},
    )

    assert resp.status_code == 404


def test_request_recovery_email_failure_is_not_hidden(anon_client):
    """SMTP failure in auth-service must not be reported as success (CP007)."""
    c, http = anon_client
    http.post.return_value = mock_resp(
        {"detail": {"errorCode": "SYSTEM_005", "message": "Recovery email could not be sent"}},
        status=503,
    )

    resp = c.post(
        "/api/v1/auth/password-recovery",
        json={"email": "inti@quechua.org"},
    )

    assert resp.status_code == 503


def test_reset_password_valid_token_returns_204(anon_client):
    """POST /api/v1/auth/password-reset with valid token → 204."""
    c, http = anon_client
    http.post.return_value = mock_resp({}, status=204)

    resp = c.post(
        "/api/v1/auth/password-reset",
        json={"token": "valid-urlsafe-token-abc123", "new_password": "NewSecure2024!"},
    )

    assert resp.status_code == 204


def test_reset_password_expired_token_returns_400(anon_client):
    """Expired or already-used recovery token → 400 from auth-service."""
    c, http = anon_client
    http.post.return_value = mock_resp(
        {"detail": "Recovery token is expired or already used"}, status=400
    )

    resp = c.post(
        "/api/v1/auth/password-reset",
        json={"token": "expired-token-xyz", "new_password": "NewSecure2024!"},
    )

    assert resp.status_code == 400
