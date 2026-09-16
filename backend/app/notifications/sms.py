import logging
import os

log = logging.getLogger("indra.notifications.sms")

_ENABLED = os.getenv("ALERT_SMS_ENABLED", "false").lower() == "true"
_TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
_TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
_TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER", "")
_ALERT_PHONE_NUMBERS = [n.strip() for n in os.getenv("ALERT_PHONE_NUMBERS", "").split(",") if n.strip()]

def send_alert_sms(message: str) -> bool:
    """Send an SMS alert via Twilio."""
    if not _ENABLED:
        log.debug("SMS alert skipped: ALERT_SMS_ENABLED is not set.")
        return False
        
    if not (_TWILIO_SID and _TWILIO_TOKEN and _TWILIO_FROM and _ALERT_PHONE_NUMBERS):
        log.warning("ALERT_SMS_ENABLED=true but Twilio config incomplete. SMS NOT sent.")
        return False
        
    try:
        from twilio.rest import Client
        client = Client(_TWILIO_SID, _TWILIO_TOKEN)
        
        for number in _ALERT_PHONE_NUMBERS:
            msg = client.messages.create(
                body=message,
                from_=_TWILIO_FROM,
                to=number
            )
            log.info("SMS sent to %s, SID: %s", number, msg.sid)
        return True
    except ImportError:
        log.warning("Twilio library not installed. SMS simulated.")
        for number in _ALERT_PHONE_NUMBERS:
            log.info("[SIMULATED SMS to %s]: %s", number, message)
        return True
    except Exception as exc:
        log.error("SMS alert FAILED: %s", exc)
        return False

def send_critical_alert_sms(event_title: str, report_count: int) -> bool:
    message = f"INDRA CRITICAL: {event_title}. {report_count} reports. Review immediately in Command Center."
    return send_alert_sms(message)
