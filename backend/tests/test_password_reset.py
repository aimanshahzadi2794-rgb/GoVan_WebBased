from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from .conftest import TestingSessionLocal, models, register_and_login


def _request_reset(client, email, caplog):
    with caplog.at_level("INFO", logger="app.routers.auth"):
        response = client.post("/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    return response


def _token_from_log(caplog):
    log_line = next(
        record.getMessage()
        for record in caplog.records
        if "Password reset link generated:" in record.getMessage()
    )
    return parse_qs(urlsplit(log_line.split(": ", 1)[1]).query)["reset_token"][0]


def test_password_reset_link_is_logged_and_token_is_one_time(client, caplog):
    register_and_login(client, "reset-user@example.com", password="OriginalPass1")
    response = _request_reset(client, "reset-user@example.com", caplog)
    token = _token_from_log(caplog)
    assert "reset_token=" in next(
        record.getMessage() for record in caplog.records
        if "Password reset link generated:" in record.getMessage()
    )

    reset = client.post(
        "/auth/reset-password",
        json={"token": token, "password": "ReplacementPass1"},
    )
    assert reset.status_code == 200
    assert client.post(
        "/auth/login",
        data={"username": "reset-user@example.com", "password": "OriginalPass1"},
    ).status_code == 401
    assert client.post(
        "/auth/login",
        data={"username": "reset-user@example.com", "password": "ReplacementPass1"},
    ).status_code == 200
    reused = client.post(
        "/auth/reset-password",
        json={"token": token, "password": "AnotherPass1"},
    )
    assert reused.status_code == 400


def test_password_reset_has_generic_response_for_unknown_email(client, caplog):
    existing = _request_reset(client, "missing-reset-user@example.com", caplog)
    assert existing.json() == {
        "message": "If an active account exists for that email, a password reset link has been generated."
    }
    assert not any(
        "Password reset link generated:" in record.getMessage()
        for record in caplog.records
    )


def test_password_reset_rejects_expired_or_invalid_tokens(client, caplog):
    register_and_login(client, "expired-reset-user@example.com")
    _request_reset(client, "expired-reset-user@example.com", caplog)
    token = _token_from_log(caplog)

    db = TestingSessionLocal()
    try:
        reset_record = db.query(models.PasswordResetToken).one()
        reset_record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    expired = client.post(
        "/auth/reset-password",
        json={"token": token, "password": "ReplacementPass1"},
    )
    assert expired.status_code == 400
    assert client.post(
        "/auth/reset-password",
        json={"token": "not-a-valid-token", "password": "ReplacementPass1"},
    ).status_code == 400


def test_password_reset_invalidates_older_links(client, caplog):
    register_and_login(client, "new-reset-user@example.com")
    _request_reset(client, "new-reset-user@example.com", caplog)
    first_token = _token_from_log(caplog)
    caplog.clear()
    _request_reset(client, "new-reset-user@example.com", caplog)
    second_token = _token_from_log(caplog)

    old_link = client.post(
        "/auth/reset-password",
        json={"token": first_token, "password": "ReplacementPass1"},
    )
    new_link = client.post(
        "/auth/reset-password",
        json={"token": second_token, "password": "ReplacementPass2"},
    )
    assert old_link.status_code == 400
    assert new_link.status_code == 200


def test_reset_password_requires_minimum_password_length(client):
    response = client.post(
        "/auth/reset-password",
        json={"token": "anything", "password": "short"},
    )
    assert response.status_code == 422
