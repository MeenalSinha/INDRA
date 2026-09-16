import logging
import os

log = logging.getLogger("indra.notifications.push")

_ENABLED = os.getenv("ALERT_PUSH_ENABLED", "false").lower() == "true"
_FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

def send_alert_push(title: str, body: str) -> bool:
    """Send a push notification (e.g. via Firebase Cloud Messaging)."""
    if not _ENABLED:
        log.debug("Push alert skipped: ALERT_PUSH_ENABLED is not set.")
        return False
        
    if not _FCM_SERVER_KEY:
        log.warning("ALERT_PUSH_ENABLED=true but FCM_SERVER_KEY missing. Push NOT sent.")
        return False
        
    try:
        # In a real app we'd use pyfcm or similar. 
        # For prototype, we log the simulated dispatch if config exists.
        log.info("[SIMULATED PUSH NOTIFICATION]: %s - %s", title, body)
        return True
    except Exception as exc:
        log.error("Push alert FAILED: %s", exc)
        return False

def send_critical_alert_push(event_title: str) -> bool:
    title = f"CRITICAL: {event_title}"
    body = "A critical weather event has been detected in your area."
    return send_alert_push(title, body)
