from unittest.mock import MagicMock, patch

import pytest

import email_service


def test_send_email_prints_when_smtp_not_configured(monkeypatch, capsys):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    email_service._send_email(
        email="test@example.com",
        subject="Test subject",
        body="Test body",
    )

    captured = capsys.readouterr()

    assert "Email to test@example.com" in captured.out
    assert "Test subject" in captured.out
    assert "Test body" in captured.out


def test_send_email_uses_smtp_when_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    monkeypatch.setenv("MAIL_FROM", "from@example.com")

    smtp_instance = MagicMock()

    with patch("email_service.smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value = smtp_instance

        email_service._send_email(
            email="test@example.com",
            subject="Test subject",
            body="Test body",
        )

        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        smtp_instance.starttls.assert_called_once()
        smtp_instance.login.assert_called_once_with("user@example.com", "password")
        smtp_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_verification_email(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")

    with patch("email_service.create_email_token", return_value="verify-token"):
        with patch("email_service._send_email") as mock_send_email:
            await email_service.send_verification_email(
                email="test@example.com",
                username="testuser",
            )

            mock_send_email.assert_called_once()

            email, subject, body = mock_send_email.call_args.args

            assert email == "test@example.com"
            assert subject == "Verify your email"
            assert "testuser" in body
            assert "http://localhost:8000/auth/verify/verify-token" in body


@pytest.mark.asyncio
async def test_send_password_reset_email(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")

    with patch("email_service.create_password_reset_token", return_value="reset-token"):
        with patch("email_service._send_email") as mock_send_email:
            await email_service.send_password_reset_email(
                email="test@example.com",
                username="testuser",
            )

            mock_send_email.assert_called_once()

            email, subject, body = mock_send_email.call_args.args

            assert email == "test@example.com"
            assert subject == "Reset your password"
            assert "testuser" in body
            assert "http://localhost:8000/auth/reset-password?token=reset-token" in body
