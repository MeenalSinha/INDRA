"""
§7 Alert email delivery.

Sends a real email when a CRITICAL alert is created, gated entirely behind
the ALERT_EMAIL_ENABLED env var (default: false). The app never becomes
dependent on SMTP being configured — if the env var is unset or credentials
are wrong, send_alert_email() logs the failure and returns without raising,
so the ingestion pipeline is not blocked.

Required env vars (all optional / off by default):
  ALERT_EMAIL_ENABLED   true to activate (default: false)
  ALERT_SMTP_HOST       e.g. smtp.gmail.com
  ALERT_SMTP_PORT       e.g. 587 (STARTTLS) or 465 (SSL)
  ALERT_SMTP_USER       sender address / login
  ALERT_SMTP_PASS       SMTP password or app-specific password
  ALERT_EMAIL_TO        comma-separated recipient list
  ALERT_EMAIL_FROM      override sender display address (defaults to SMTP user)

No third-party library needed — uses Python's stdlib smtplib + email.mime.
BUILT status: BUILT-AND-VERIFIED if SMTP credentials are provided;
BUILT-BUT-UNTESTED if env vars are absent (the code path is exercised by
test_email_delivery_skips_when_disabled in the new test file).
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger("indra.notifications.email")

_ENABLED = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true"
_SMTP_HOST = os.getenv("ALERT_SMTP_HOST", "")
_SMTP_PORT = int(os.getenv("ALERT_SMTP_PORT", "587"))
_SMTP_USER = os.getenv("ALERT_SMTP_USER", "")
_SMTP_PASS = os.getenv("ALERT_SMTP_PASS", "")
_EMAIL_TO = [a.strip() for a in os.getenv("ALERT_EMAIL_TO", "").split(",") if a.strip()]
_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", _SMTP_USER)


def send_alert_email(subject: str, body: str) -> bool:
    """Send a plain-text alert email.

    Returns True if sent, False if skipped or failed (never raises).
    Skips silently when ALERT_EMAIL_ENABLED is false — this is the
    intended behaviour so the demo needs no SMTP config.
    """
    if not _ENABLED:
        log.debug("Alert email skipped: ALERT_EMAIL_ENABLED is not set.")
        return False

    if not (_SMTP_HOST and _SMTP_USER and _EMAIL_TO):
        log.warning(
            "ALERT_EMAIL_ENABLED=true but SMTP config incomplete "
            "(need ALERT_SMTP_HOST, ALERT_SMTP_USER, ALERT_EMAIL_TO). "
            "Email NOT sent."
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = _EMAIL_FROM or _SMTP_USER
    msg["To"] = ", ".join(_EMAIL_TO)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if _SMTP_PORT == 465:
            # SSL from the start
            with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, timeout=10) as server:
                if _SMTP_PASS:
                    server.login(_SMTP_USER, _SMTP_PASS)
                server.sendmail(_SMTP_USER, _EMAIL_TO, msg.as_string())
        else:
            # STARTTLS (port 587 default)
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if _SMTP_PASS:
                    server.login(_SMTP_USER, _SMTP_PASS)
                server.sendmail(_SMTP_USER, _EMAIL_TO, msg.as_string())
        log.info("Alert email sent to %s: %s", _EMAIL_TO, subject)
        return True
    except Exception as exc:
        log.error("Alert email FAILED (%s): %s", type(exc).__name__, exc)
        return False


def send_critical_alert_email(event_title: str, report_count: int, confidence: float) -> bool:
    """Convenience wrapper called from ingestion/adapters.py on CRITICAL transition."""
    subject = f"[INDRA CRITICAL] {event_title}"
    body = (
        f"CRITICAL weather event detected by INDRA.\n\n"
        f"Event: {event_title}\n"
        f"Reports: {report_count}\n"
        f"Fusion confidence: {round(confidence * 100)}%\n\n"
        f"Open the INDRA command centre to review and verify.\n"
    )
    return send_alert_email(subject, body)
