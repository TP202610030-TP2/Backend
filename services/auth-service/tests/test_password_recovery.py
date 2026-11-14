from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from unittest.mock import patch

from app.core.exceptions import EmailDeliveryError, TokenInvalidError, UserNotFoundError
from app.core.security import verify_password
from app.models.credential import PasswordRecoveryToken
from app.services.auth_service import AuthService


def _make_service():
    svc = AuthService(MagicMock())
    svc._credentials = AsyncMock()
    svc._blocklist = AsyncMock()
    svc._recovery = AsyncMock()
    return svc


def _recovery_entry(used: bool = False, expired: bool = False) -> MagicMock:
    entry = MagicMock(spec=PasswordRecoveryToken)
    entry.user_id = "user-xyz"
    entry.email = "user@example.com"
    entry.used = used
    entry.expires_at = (
        datetime.now(timezone.utc) - timedelta(hours=2)
        if expired
        else datetime.now(timezone.utc) + timedelta(hours=1)
    )
    return entry


async def test_initiate_recovery_creates_token_for_known_email():
    svc = _make_service()
    svc._credentials.get_by_email.return_value = MagicMock(
        user_id="user-xyz", account_status="active"
    )

    await svc.initiate_recovery("user@example.com")

    svc._recovery.create.assert_called_once()
    call_args = svc._recovery.create.call_args
    assert call_args.args[1] == "user-xyz"
    assert call_args.args[2] == "user@example.com"


async def test_initiate_recovery_unknown_email_raises_not_found():
    """CP008: the user must be told that no account exists for the email."""
    svc = _make_service()
    svc._credentials.get_by_email.return_value = None

    with pytest.raises(UserNotFoundError) as exc_info:
        await svc.initiate_recovery("nobody@example.com")

    assert exc_info.value.status_code == 404
    svc._recovery.create.assert_not_called()


async def test_initiate_recovery_sends_email_with_token():
    svc = _make_service()
    svc._credentials.get_by_email.return_value = MagicMock(
        user_id="user-xyz", account_status="active"
    )

    with patch("app.services.auth_service.send_recovery_email", new=AsyncMock()) as send:
        await svc.initiate_recovery("user@example.com")

    send.assert_awaited_once()
    token = svc._recovery.create.call_args.args[0]
    assert send.call_args.args[0] == "user@example.com"
    assert send.call_args.args[1] == token


async def test_initiate_recovery_smtp_failure_raises_503():
    """CP007: a delivery failure must not be reported as success."""
    svc = _make_service()
    svc._credentials.get_by_email.return_value = MagicMock(
        user_id="user-xyz", account_status="active"
    )

    with patch(
        "app.services.auth_service.send_recovery_email",
        new=AsyncMock(side_effect=OSError("smtp down")),
    ):
        with pytest.raises(EmailDeliveryError) as exc_info:
            await svc.initiate_recovery("user@example.com")

    assert exc_info.value.status_code == 503


async def test_reset_password_valid_token_updates_hash():
    svc = _make_service()
    svc._recovery.get_valid.return_value = _recovery_entry()

    await svc.reset_password("valid_token_xyz", "NewPass123!")

    svc._credentials.update_password.assert_called_once()
    call_args = svc._credentials.update_password.call_args
    assert call_args.args[0] == "user-xyz"
    new_hash = call_args.args[1]
    assert verify_password("NewPass123!", new_hash)


async def test_reset_password_marks_token_used():
    svc = _make_service()
    svc._recovery.get_valid.return_value = _recovery_entry()

    await svc.reset_password("valid_token_xyz", "NewPass123!")

    svc._recovery.mark_used.assert_called_once_with("valid_token_xyz")


async def test_reset_password_invalid_token_raises():
    svc = _make_service()
    svc._recovery.get_valid.return_value = None

    with pytest.raises(TokenInvalidError):
        await svc.reset_password("bad_token", "NewPass123!")

    svc._credentials.update_password.assert_not_called()


async def test_reset_password_expired_token_raises():
    """get_valid returns None for expired tokens (repo filters them out)."""
    svc = _make_service()
    svc._recovery.get_valid.return_value = None

    with pytest.raises(TokenInvalidError):
        await svc.reset_password("expired_token", "NewPass123!")
