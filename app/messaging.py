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


def render_for_contact(text: str, contact, org_name: str = "") -> str:
    """Replace {name} and {org} placeholders safely without crashing on extra braces."""
    recipient = (contact.name or "").strip() or "Valued Guest"
    result = (text or "").replace("{name}", recipient)
    if org_name:
        result = result.replace("{org}", org_name)
    return result


def send_message(channel, contact, message, provider, org_name: str = "", unsubscribe_url: str = ""):
    reason = skip_reason(channel, contact)
    if reason:
        return SendResult("skipped", reason)

    subject = render_for_contact(message.subject, contact, org_name)
    body = render_for_contact(message.body, contact, org_name)
    if channel == "email" and unsubscribe_url:
        body = f"{body}\n\n---\nTo stop receiving these greetings, unsubscribe here: {unsubscribe_url}"

    try:
        return provider.send(
            channel, address_for(channel, contact), subject, body
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


def send_batch(message, contacts, channel, provider, org_name: str = "", unsubscribe_url_fn=None):
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
        unsub_url = unsubscribe_url_fn(contact) if (channel == "email" and unsubscribe_url_fn) else ""
        result = send_message(
            channel,
            contact,
            message,
            provider,
            org_name=org_name,
            unsubscribe_url=unsub_url,
        )
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


def analyze_sms(body: str) -> dict:
    """Estimate Nigerian SMS encoding, part count, and billing warnings."""
    text = body or ""
    non_ascii = sorted({ch for ch in text if ord(ch) > 127})
    is_unicode = bool(non_ascii)

    if is_unicode:
        single_limit, multi_limit = 70, 67
    else:
        single_limit, multi_limit = 160, 153

    length = len(text)
    if length == 0:
        parts = 0
    elif length <= single_limit:
        parts = 1
    else:
        parts = (length + multi_limit - 1) // multi_limit

    warnings = []
    if is_unicode:
        sample = "".join(non_ascii[:5])
        warnings.append(
            f"Contains non-GSM characters ({sample}); networks drop the limit from 160 to 70 chars per SMS."
        )
    if parts > 1:
        warnings.append(
            f"Message is {length} chars and will be billed as {parts} SMS parts per recipient."
        )

    return {
        "length": length,
        "parts": parts,
        "limit": single_limit,
        "is_unicode": is_unicode,
        "warnings": warnings,
    }


class LiveProvider:
    """Sends real emails via Brevo and real Nigerian SMS via Termii."""

    def __init__(self, config):
        self.brevo_key = config.get("BREVO_API_KEY", "")
        self.brevo_sender_email = config.get("BREVO_SENDER_EMAIL", "")
        self.brevo_sender_name = config.get("BREVO_SENDER_NAME", "Salutia")
        self.termii_key = config.get("TERMII_API_KEY", "")
        self.termii_sender_id = config.get("TERMII_SENDER_ID", "Salutia")
        self.termii_channel = config.get("TERMII_CHANNEL", "dnd")
        self.fallback = ConsoleProvider()

    def send(self, channel, to, subject, body):
        if channel == "email":
            if not self.brevo_key or not self.brevo_sender_email:
                return self.fallback.send(channel, to, subject, body)
            return self._send_brevo(to, subject, body)

        if channel == "sms":
            if not self.termii_key:
                return self.fallback.send(channel, to, subject, body)
            return self._send_termii(to, body)

        raise ValueError(f"unknown channel: {channel}")

    def _send_brevo(self, to_email, subject, body):
        import json
        import urllib.request

        payload = json.dumps(
            {
                "sender": {
                    "name": self.brevo_sender_name,
                    "email": self.brevo_sender_email,
                },
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://brevo.com",
            data=payload,
            headers={
                "api-key": self.brevo_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= resp.status < 300:
                return SendResult("sent")
            return SendResult("failed", f"Brevo HTTP {resp.status}")

    def _send_termii(self, to_phone, body):
        import json
        import urllib.request

        msisdn = to_phone.lstrip("+")
        payload = json.dumps(
            {
                "to": msisdn,
                "from": self.termii_sender_id,
                "sms": body,
                "type": "plain",
                "channel": self.termii_channel,
                "api_key": self.termii_key,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://termii.com",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == "ok" or resp.status == 200:
                return SendResult("sent")
            return SendResult("failed", data.get("message", "Termii send failed"))
