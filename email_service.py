import os
import smtplib
from email.message import EmailMessage

from auth import create_email_token


async def send_verification_email(email: str, username: str) -> None:
    token = create_email_token(email)
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
    verify_url = f"{base_url}/auth/verify/{token}"

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM", smtp_user or "noreply@example.com")

    subject = "Verify your email"
    body = f"Hello, {username}!\n\nPlease verify your email: {verify_url}\n"

    if not smtp_host or not smtp_user or not smtp_password:
        print(f"Verification email for {email}: {verify_url}")
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
