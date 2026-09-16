"""
Verification workflow: UNVERIFIED -> UNDER_REVIEW -> PROBABLE -> VERIFIED
                                                                -> REJECTED
Every state change is written to VerificationAction (event-scoped receipt)
and AuditLog (global trail), matching the spec's audit requirements.
"""
import datetime as dt
from .. import models


def _log(db, event, action, admin_name, reason, previous_state, new_state):
    db.add(models.VerificationAction(
        event_id=event.id, action=action, admin_name=admin_name, reason=reason,
        previous_state=previous_state, new_state=new_state,
    ))
    db.add(models.AuditLog(
        actor=admin_name, action=action, target_type="event", target_id=event.id,
        details={"reason": reason, "previous_state": previous_state, "new_state": new_state},
    ))


def verify_event(db, event_id: int, admin_name: str = "Sixth Sense Admin", reason: str = ""):
    event = db.query(models.Event).get(event_id)
    if not event:
        return None
    previous = event.verification_status
    event.verification_status = "VERIFIED"
    event.verified_report_count = event.report_count
    timeline = list(event.timeline or [])
    timeline.append({"time": dt.datetime.utcnow().isoformat(), "label": f"Verified by {admin_name}"})
    event.timeline = timeline
    _log(db, event, "VERIFY", admin_name, reason, previous, "VERIFIED")
    db.commit()
    db.refresh(event)
    return event


def reject_event(db, event_id: int, admin_name: str = "Sixth Sense Admin", reason: str = ""):
    event = db.query(models.Event).get(event_id)
    if not event:
        return None
    previous = event.verification_status
    event.verification_status = "REJECTED"
    timeline = list(event.timeline or [])
    timeline.append({"time": dt.datetime.utcnow().isoformat(), "label": f"Rejected by {admin_name}: {reason or 'no reason given'}"})
    event.timeline = timeline
    _log(db, event, "REJECT", admin_name, reason, previous, "REJECTED")
    db.commit()
    db.refresh(event)
    return event


def request_more_evidence(db, event_id: int, admin_name: str = "Sixth Sense Admin", reason: str = ""):
    event = db.query(models.Event).get(event_id)
    if not event:
        return None
    previous = event.verification_status
    event.verification_status = "UNDER_REVIEW"
    timeline = list(event.timeline or [])
    timeline.append({"time": dt.datetime.utcnow().isoformat(), "label": "More evidence requested"})
    event.timeline = timeline
    _log(db, event, "REQUEST_MORE_EVIDENCE", admin_name, reason, previous, "UNDER_REVIEW")
    db.commit()
    db.refresh(event)
    return event


def escalate_event(db, event_id: int, admin_name: str = "Sixth Sense Admin", reason: str = ""):
    event = db.query(models.Event).get(event_id)
    if not event:
        return None
    previous = event.severity
    order = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    idx = order.index(previous) if previous in order else 0
    event.severity = order[min(idx + 1, len(order) - 1)]
    _log(db, event, "ESCALATE", admin_name, reason, previous, event.severity)
    db.commit()
    db.refresh(event)
    return event


def set_severity(db, event_id: int, new_severity: str, admin_name: str = "Sixth Sense Admin", reason: str = ""):
    event = db.query(models.Event).get(event_id)
    if not event:
        return None
    previous = event.severity
    event.severity = new_severity
    _log(db, event, "SEVERITY_CHANGE", admin_name, reason, previous, new_severity)
    db.commit()
    db.refresh(event)
    return event


def mark_report_duplicate(db, report_id: int, duplicate_of: int, admin_name: str = "Sixth Sense Admin"):
    report = db.query(models.Report).get(report_id)
    if not report:
        return None
    report.duplicate_status = "LIKELY_DUPLICATE"
    report.duplicate_of_report_id = duplicate_of
    db.add(models.AuditLog(
        actor=admin_name, action="MARK_DUPLICATE", target_type="report", target_id=report_id,
        details={"duplicate_of": duplicate_of},
    ))
    db.commit()
    db.refresh(report)
    return report
