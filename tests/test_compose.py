from werkzeug.security import generate_password_hash
import pytest
from app import create_app, db
from app.models import Contact, Message, Organisation, SendLog, User, utcnow
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        org = Organisation(name="St. Anne's Academy", sender_type="school")
        db.session.add(org)
        db.session.flush()

        user = User(org_id=org.id, email="admin@school.ng", password_hash=generate_password_hash("secret123"))
        db.session.add(user)

        # Contact 1: eligible for SMS only
        c1 = Contact(
            org_id=org.id,
            name="Mrs. Ochanya",
            phone="+2348031234567",
            sms_consented_at=utcnow(),
        )
        # Contact 2: no consent recorded (should be skipped)
        c2 = Contact(
            org_id=org.id,
            name="Mr. Musa",
            phone="+2348098765432",
        )
        db.session.add_all([c1, c2])
        db.session.commit()

        with app.test_client() as test_client:
            test_client.post(
                "/login",
                data={"email": "admin@school.ng", "password": "secret123"},
            )
            yield test_client, app


def test_compose_preview_and_send_batch(client):
    test_client, app = client

    # 1. Create a new message
    resp = test_client.post(
        "/messages/new",
        data={
            "subject": "Term Resumption",
            "body": "School resumes on Monday at 8am.",
            "season": "First Term",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Term Resumption" in resp.data
    assert b"Audience Preview" in resp.data

    with app.app_context():
        msg = Message.query.first()
        msg_id = msg.id

    # 2. Send batch over SMS
    resp = test_client.post(
        f"/messages/{msg_id}/send",
        data={"channel": "sms"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Sent 1, skipped 1, failed 0, already sent 0." in resp.data

    # 3. Sending again must not double-send to c1
    resp = test_client.post(
        f"/messages/{msg_id}/send",
        data={"channel": "sms"},
        follow_redirects=True,
    )
    assert b"Sent 0, skipped 1, failed 0, already sent 1." in resp.data

    with app.app_context():
        assert len(app.extensions["message_provider"].outbox) == 1
        assert SendLog.query.count() == 3


def test_personalization_and_one_click_unsubscribe(client):
    test_client, app = client

    with app.app_context():
        c1 = Contact.query.filter_by(name="Mrs. Ochanya").first()
        c1.email = "ochanya@example.com"
        c1.email_consented_at = utcnow()
        db.session.commit()

    # Create a personalized message with {name} and {org}
    test_client.post(
        "/messages/new",
        data={
            "subject": "Hello {name}",
            "body": "Welcome {name} to {org}!",
            "season": "Term 1",
        },
    )
    with app.app_context():
        msg = Message.query.order_by(Message.id.desc()).first()
        msg_id = msg.id

    # Send email and check personalized text + unsubscribe link
    test_client.post(f"/messages/{msg_id}/send", data={"channel": "email"})
    with app.app_context():
        sent_item = app.extensions["message_provider"].outbox[-1]
        assert sent_item["subject"] == "Hello Mrs. Ochanya"
        assert "Welcome Mrs. Ochanya to St. Anne's Academy!" in sent_item["body"]
        assert "/contacts/unsubscribe/" in sent_item["body"]

        # Extract unsubscribe URL and visit it as a recipient
        unsub_url = sent_item["body"].split("unsubscribe here: ")[1].strip()
        path = unsub_url.replace("http://localhost", "")

    resp = test_client.get(path)
    assert resp.status_code == 200
    assert b"You are unsubscribed" in resp.data

    with app.app_context():
        c1 = Contact.query.filter_by(name="Mrs. Ochanya").first()
        assert c1.email_opted_out_at is not None
