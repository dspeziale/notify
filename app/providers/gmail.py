"""Gmail / Email API provider supporting Google App Passwords (SMTP) and OAuth 2.0."""

import base64
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import logging
from typing import Any
import httpx
from app.core.config import settings
from app.providers.base import BaseNotificationProvider, ProviderResult

try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None

logger = logging.getLogger(__name__)


class GmailProvider(BaseNotificationProvider):
    """Integrates with Google Gmail via App Passwords (SMTP) or OAuth2 REST API."""

    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    SEND_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

    def __init__(
        self,
        email_address: str,
        auth_type: str | None = None,
        app_password: str | None = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        access_token: str | None = None,
        token_expiry: datetime | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.email_address = email_address
        if auth_type:
            self.auth_type = auth_type
        elif app_password:
            self.auth_type = "app_password"
        elif client_id or refresh_token or access_token:
            self.auth_type = "oauth2"
        else:
            self.auth_type = "app_password"

        self.app_password = app_password.replace(" ", "") if app_password else None
        self.smtp_host = smtp_host or "smtp.gmail.com"
        self.smtp_port = smtp_port or 587

        # OAuth credentials
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.token_expiry = token_expiry
        self._client = client

    def _build_email_message(self, payload: dict[str, Any]) -> EmailMessage:
        """Constructs an RFC 2822 EmailMessage instance."""
        msg = EmailMessage()
        msg["From"] = self.email_address
        msg["To"] = ", ".join(payload.get("to", []))
        if payload.get("cc"):
            msg["Cc"] = ", ".join(payload["cc"])
        if payload.get("bcc"):
            msg["Bcc"] = ", ".join(payload["bcc"])
        msg["Subject"] = payload.get("subject", "Notification")

        text_body = payload.get("text")
        html_body = payload.get("html")

        if text_body:
            msg.set_content(text_body)
            if html_body:
                msg.add_alternative(html_body, subtype="html")
        elif html_body:
            msg.set_content(html_body, subtype="html")
        else:
            msg.set_content("")

        # Handle attachments
        for att in payload.get("attachments", []):
            filename = att.get("filename", "attachment")
            content_b64 = att.get("content_base64", "")
            raw_bytes = base64.b64decode(content_b64)

            if len(raw_bytes) > settings.MAX_ATTACHMENT_SIZE_BYTES:
                raise ValueError(
                    f"Attachment '{filename}' exceeds maximum allowed size of {settings.MAX_ATTACHMENT_SIZE_BYTES} bytes"
                )

            content_type = att.get("content_type", "application/octet-stream")
            if "/" in content_type:
                maintype, subtype = content_type.split("/", 1)
            else:
                maintype, subtype = "application", "octet-stream"

            msg.add_attachment(
                raw_bytes,
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )
        return msg

    async def _send_smtp(self, payload: dict[str, Any]) -> ProviderResult:
        """Sends an email using Google App Password via secure SMTP."""
        if not self.app_password:
            return ProviderResult(
                success=False,
                error_code="MISSING_APP_PASSWORD",
                error_message="No App Password configured for this email account",
                is_transient=False,
            )

        try:
            msg = self._build_email_message(payload)
        except ValueError as e:
            return ProviderResult(
                success=False,
                error_code="ATTACHMENT_TOO_LARGE",
                error_message=str(e),
                is_transient=False,
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                error_code="MESSAGE_BUILD_FAILED",
                error_message=f"Failed to build email message: {e}",
                is_transient=False,
            )

        try:
            is_starttls = self.smtp_port == 587
            is_ssl = self.smtp_port == 465

            response = await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                start_tls=is_starttls,
                use_tls=is_ssl,
                username=self.email_address,
                password=self.app_password,
                timeout=settings.NOTIFICATION_TIMEOUT_SECONDS,
            )

            # Response is typically a tuple of (code, message)
            code = getattr(response, "code", 250) if hasattr(response, "code") else 250
            return ProviderResult(
                success=True,
                provider_message_id=f"smtp_{int(datetime.now().timestamp())}",
                status_code=code,
            )

        except aiosmtplib.errors.SMTPAuthenticationError as auth_err:
            logger.error("Gmail SMTP authentication failed: %s", auth_err)
            return ProviderResult(
                success=False,
                error_code="SMTP_AUTH_FAILED",
                error_message="Invalid Gmail App Password or username. Check Google App Password settings.",
                is_transient=False,
                status_code=auth_err.code if hasattr(auth_err, "code") else 535,
            )
        except (aiosmtplib.errors.SMTPServerDisconnected, aiosmtplib.errors.SMTPConnectError, TimeoutError) as net_err:
            logger.warning("Gmail SMTP connection/timeout error: %s", net_err)
            return ProviderResult(
                success=False,
                error_code="SMTP_CONNECTION_ERROR",
                error_message=f"Transient connection error contacting {self.smtp_host}: {net_err}",
                is_transient=True,
            )
        except aiosmtplib.errors.SMTPResponseException as smtp_err:
            code = smtp_err.code
            is_transient = 400 <= code < 500
            return ProviderResult(
                success=False,
                error_code=f"SMTP_ERROR_{code}",
                error_message=str(smtp_err.message),
                is_transient=is_transient,
                status_code=code,
            )
        except Exception as exc:
            logger.error("Unexpected error sending email via SMTP: %s", exc)
            return ProviderResult(
                success=False,
                error_code="SMTP_UNEXPECTED_ERROR",
                error_message=f"Failed to send email: {exc}",
                is_transient=False,
            )

    async def _send_oauth(self, payload: dict[str, Any]) -> ProviderResult:
        """Sends an email using Google OAuth2 REST API."""
        try:
            access_token, token_updates = await self._ensure_valid_access_token()
        except Exception as exc:
            logger.error("Gmail OAuth token retrieval failed: %s", exc)
            return ProviderResult(
                success=False,
                error_code="GMAIL_AUTH_FAILED",
                error_message=str(exc),
                is_transient=False,
            )

        try:
            msg = self._build_email_message(payload)
            raw_mime_base64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        except ValueError as val_err:
            return ProviderResult(
                success=False,
                error_code="ATTACHMENT_TOO_LARGE",
                error_message=str(val_err),
                is_transient=False,
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                error_code="MIME_BUILD_FAILED",
                error_message=f"Failed to build MIME message: {str(exc)}",
                is_transient=False,
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        send_body = {"raw": raw_mime_base64}

        try:
            if self._client:
                response = await self._client.post(
                    self.SEND_ENDPOINT,
                    headers=headers,
                    json=send_body,
                    timeout=settings.NOTIFICATION_TIMEOUT_SECONDS,
                )
            else:
                async with httpx.AsyncClient(timeout=settings.NOTIFICATION_TIMEOUT_SECONDS) as client:
                    response = await client.post(self.SEND_ENDPOINT, headers=headers, json=send_body)

            status_code = response.status_code
            data = response.json() if "application/json" in response.headers.get("content-type", "") else {}

            if status_code == 200:
                message_id = data.get("id")
                return ProviderResult(
                    success=True,
                    provider_message_id=message_id,
                    status_code=status_code,
                    new_tokens=token_updates,
                )

            error_info = data.get("error", {})
            error_message = error_info.get("message", response.text)
            is_transient = status_code == 429 or status_code >= 500

            return ProviderResult(
                success=False,
                status_code=status_code,
                error_code=f"GMAIL_ERROR_{status_code}",
                error_message=error_message,
                is_transient=is_transient,
                new_tokens=token_updates,
            )

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(
                success=False,
                error_code="NETWORK_TIMEOUT",
                error_message=f"Network error contacting Gmail API: {str(exc)}",
                is_transient=True,
                new_tokens=token_updates,
            )
        except Exception as exc:
            return ProviderResult(
                success=False,
                error_code="UNEXPECTED_ERROR",
                error_message=f"Unexpected error: {str(exc)}",
                is_transient=False,
                new_tokens=token_updates,
            )

    async def _ensure_valid_access_token(self) -> tuple[str, dict[str, Any] | None]:
        """Ensures OAuth access token is valid, refreshing if needed."""
        now = datetime.now(timezone.utc)
        if self.access_token and self.token_expiry and (self.token_expiry - now).total_seconds() > 60:
            return self.access_token, None

        if not self.refresh_token:
            raise ValueError("Gmail configuration lacks a refresh token. Please complete OAuth flow.")

        refresh_payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }

        if self._client:
            res = await self._client.post(self.TOKEN_ENDPOINT, data=refresh_payload)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.TOKEN_ENDPOINT, data=refresh_payload)

        if res.status_code != 200:
            raise RuntimeError(f"Failed to refresh Google OAuth token (HTTP {res.status_code}): {res.text}")

        token_data = res.json()
        new_access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        new_expiry = now + timedelta(seconds=expires_in)

        self.access_token = new_access_token
        self.token_expiry = new_expiry

        return new_access_token, {"access_token": new_access_token, "token_expiry": new_expiry}

    async def send(self, payload: dict[str, Any]) -> ProviderResult:
        """Dispatches notification via App Password (SMTP) or OAuth2 REST API."""
        if self.auth_type == "app_password":
            return await self._send_smtp(payload)
        return await self._send_oauth(payload)
