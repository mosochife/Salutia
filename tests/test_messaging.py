from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import create_app, db
from app.messaging import ConsoleProvider, log_send, send_message
from app.models import Contact, Message, Organisation
from config import Config

NOW = datetime.now(timezone.utc)
MESSAGE = SimpleNamespace(subject="Merry Christmas", body="Warm wishes from us.")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


def make_contact(**overrides):
    fields = dict(
        email="ada@example.com",
        phone="+2348012345678",
        email_consented_at=NOW,
        sms_consented_at=NOW,
        email_opted_out_at=None,
        sms_opted_out_at=None,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_email_is_sent_to_the_email_address():
    provider = ConsoleProvider()
    result = send_message("email", make_contact(), MESSAGE, provider)
    assert result.status == "sent"
    assert provider.outbox[0]["to"] == "ada@example.com"


def test_sms_is_sent_to_the_phone_number():
    provider = ConsoleProvider()
    result = send_message("sms", make_contact(), MESSAGE, provider)
    assert result.status == "sent"
    assert provider.outbox[0]["to"] == "+2348012345678"


def test_no_consent_is_skipped():
    provider = ConsoleProvider()
    contact = make_contact(sms_consented_at=None)
    result = send_message("sms", contact, MESSAGE, provider)
    assert result.status == "skipped"
    assert provider.outbox == []


def test_opted_out_is_skipped():
    provider = ConsoleProvider()
    contact = make_contact(email_opted_out_at=NOW)
    result = send_message("email", contact, MESSAGE, provider)
    assert result.status == "skipped"
    assert provider.outbox == []


def test_missing_address_is_skipped():
    provider = ConsoleProvider()
    result = send_message("sms", make_contact(phone=None), MESSAGE, provider)
    assert result.status == "skipped"
    assert provider.outbox == []


def test_consent_is_per_channel():
    provider = ConsoleProvider()
    contact = make_contact(sms_consented_at=None)
    assert send_message("email", contact, MESSAGE, provider).status == "sent"
    assert send_message("sms", contact, MESSAGE, provider).status == "skipped"


def test_unknown_channel_raises():
    with pytest.raises(ValueError):
        send_message("fax", make_contact(), MESSAGE, ConsoleProvider())


def test_provider_error_becomes_failed():
    class BrokenProvider:
        def send(self, channel, to, subject, body):
            raise RuntimeError("boom")

    result = send_message("email", make_contact(), MESSAGE, BrokenProvider())
    assert result.status == "failed"
    assert "boom" in result.detail


def test_log_send_writes_a_row(app):
    org = Organisation(name="A", sender_type="school")
    db.session.add(org)
    db.session.commit()
    contact = Contact(org_id=org.id, email="ada@example.com", email_consented_at=NOW)
    message = Message(org_id=org.id, subject="Hi", body="Hello")
    db.session.add_all([contact, message])
    db.session.commit()

    result = send_message("email", contact, message, ConsoleProvider())
    row = log_send(message, contact, "email", result)

    assert row.status == "sent"
    assert row.channel == "email"
    assert row.sent_at is not None


def test_analyze_sms_plain_gsm():
    from app.messaging import analyze_sms

    info = analyze_sms("Resumption is Monday 8am.")
    assert info["parts"] == 1
    assert info["limit"] == 160
    assert info["warnings"] == []


def test_analyze_sms_splits_over_160_and_warns_on_emoji():
    from app.messaging import analyze_sms

    long_info = analyze_sms("A" * 161)
    assert long_info["parts"] == 2
    assert len(long_info["warnings"]) == 1

    emoji_info = analyze_sms("Happy New Term 🎉")
    assert emoji_info["is_unicode"] is True
    assert emoji_info["limit"] == 70
    assert len(emoji_info["warnings"]) == 1
