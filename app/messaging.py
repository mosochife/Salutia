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


def send_message(channel, contact, message, provider):
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel: {channel}")

    to = contact.email if channel == "email" else contact.phone
    if not to:
        return SendResult("skipped", f"contact has no {channel} address")

    if getattr(contact, f"{channel}_opted_out_at") is not None:
        return SendResult("skipped", "contact opted out")
    if getattr(contact, f"{channel}_consented_at") is None:
        return SendResult("skipped", "no consent recorded")

    try:
        return provider.send(channel, to, message.subject, message.body)
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
