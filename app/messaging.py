from dataclasses import dataclass

from app import db
from app.models import SendLog, utcnow

CHANNELS = ("email", "sms")


@dataclass
class SendResult:
    status: str  # "sent", "skipped" or "failed"
    detail: str = ""


class ConsoleProvider:
    """Test provider: records messages in memory instead of sending them."""

    def __init__(self):
        self.outbox = []

    def send(self, channel, to, subject, body):
        self.outbox.append(
            {"channel": channel, "to": to, "subject": subject, "body": body}
        )
        print(f"[{channel}] to={to} subject={subject!r} body={body!r}")
        return SendResult("sent")


def address_for(channel, contact):
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel: {channel}")
    return contact.email if channel == "email" else contact.phone


def skip_reason(channel, contact):
    """Why this contact cannot receive this channel, or None if they can."""
    if not address_for(channel, contact):
        return f"contact has no {channel} address"
    if getattr(contact, f"{channel}_opted_out_at") is not None:
        return "contact opted out"
    if getattr(contact, f"{channel}_consented_at") is None:
        return "no consent recorded"
    return None


def send_message(channel, contact, message, provider):
    reason = skip_reason(channel, contact)
    if reason:
        return SendResult("skipped", reason)
    try:
        return provider.send(
            channel, address_for(channel, contact), message.subject, message.body
        )
    except Exception as exc:  # one bad send must not crash a whole batch
        return SendResult("failed", str(exc))


def log_send(message, contact, channel, result):
    row = SendLog(
        message_id=message.id,
        contact_id=contact.id,
        channel=channel,
        status=result.status,
        sent_at=utcnow() if result.status == "sent" else None,
        error=None if result.status == "sent" else result.detail,
    )
    db.session.add(row)
    db.session.commit()
    return row


def send_batch(message, contacts, channel, provider):
    """Send one message to many contacts and return counts by outcome."""
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel: {channel}")

    already_sent = {
        row.contact_id
        for row in SendLog.query.filter_by(
            message_id=message.id, channel=channel, status="sent"
        )
    }
    counts = {"sent": 0, "skipped": 0, "failed": 0, "already_sent": 0}
    for contact in contacts:
        if contact.id in already_sent:
            counts["already_sent"] += 1
            continue
        result = send_message(channel, contact, message, provider)
        counts[result.status] += 1
        db.session.add(
            SendLog(
                message_id=message.id,
                contact_id=contact.id,
                channel=channel,
                status=result.status,
                sent_at=utcnow() if result.status == "sent" else None,
                error=None if result.status == "sent" else result.detail,
            )
        )
    if counts["sent"]:
        message.status = "sent"
    db.session.commit()
    return counts
