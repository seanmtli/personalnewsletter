import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings

settings = get_settings()


class EmailService:
    """Email service supporting Resend API and SMTP fallback."""

    async def send(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Send an email using the configured provider.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body

        Returns:
            True if sent successfully, False otherwise
        """
        # Try Resend first
        if settings.resend_api_key:
            return await self._send_resend(to_email, subject, html_content)

        # Fall back to SMTP
        if settings.smtp_host and settings.smtp_user:
            return await self._send_smtp(to_email, subject, html_content)

        print("No email provider configured")
        return False

    async def _send_resend(
        self, to_email: str, subject: str, html_content: str
    ) -> bool:
        """Send email using Resend API."""
        try:
            import resend

            resend.api_key = settings.resend_api_key

            params = {
                "from": settings.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            resend.Emails.send(params)
            return True

        except Exception as e:
            print(f"Resend error: {e}")
            return False

    async def _send_smtp(
        self, to_email: str, subject: str, html_content: str
    ) -> bool:
        """Send email using SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.from_email
            msg["To"] = to_email

            # Attach HTML content
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Connect and send
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.from_email, to_email, msg.as_string())

            return True

        except Exception as e:
            print(f"SMTP error: {e}")
            return False
