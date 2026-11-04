import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger(__name__)


class EmailSender(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleSender(EmailSender):
    """Development only: prints the email to the server terminal."""

    def send(self, to, subject, body):
        print(f"\n--- DEV EMAIL ---\nTo: {to}\nSubject: {subject}\n\n{body}\n-----------------\n",
              flush=True)


class SMTPSender(EmailSender):
    def send(self, to, subject, body):
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)


def get_sender() -> EmailSender:
    if settings.email_provider == "smtp" and settings.smtp_host:
        return SMTPSender()
    return ConsoleSender()


def send_reset_email(to: str, token: str) -> None:
    body = (
        "We received a request to reset your password.\n\n"
        f"Your reset token (valid for 1 hour, single use):\n\n{token}\n\n"
        "If you did not request this, ignore this email. Your password has not changed."
    )
    try:
        get_sender().send(to, "Reset your password", body)
    except Exception:
        # Never log the token or the address, and never fail the request over email trouble
        log.exception("Password reset email could not be sent")
