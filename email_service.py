"""Email delivery helpers for verification and password reset flows."""

import os
import smtplib
from email.message import EmailMessage

from auth import create_email_token, create_password_reset_token


def _send_email(email: str, subject: str, body: str) -> None:
    """Send an email through SMTP or print it when SMTP is not configured."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM", smtp_user or "noreply@example.com")

    if not smtp_host or not smtp_user or not smtp_password:
        print(f"Email to {email}: {subject}\n{body}")
        return

    message = EmailMessage()
    message["From"] = mail_from
    message["To"] = email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


async def send_verification_email(email: str, username: str) -> None:
    """Send an email verification link to a user."""
    token = create_email_token(email)
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
    verify_url = f"{base_url}/auth/verify/{token}"
    body = f"Hello, {username}!\n\nPlease verify your email: {verify_url}\n"
    _send_email(email, "Verify your email", body)


async def send_password_reset_email(email: str, username: str) -> None:
    """Send a password reset link containing a scoped JWT token."""
    token = create_password_reset_token(email)
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
    reset_url = f"{base_url}/auth/reset-password?token={token}"
    body = f"Hello, {username}!\n\nUse this link to reset your password: {reset_url}\n"
    _send_email(email, "Reset your password", body)
