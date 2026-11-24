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
        org = Organisation(name="St. Anne's Academy", kind="school")
        db.session.add(org)
        db.session.flush()

        user = User(org_id=org.id, email="admin@school.ng")
        user.set_password("secret123")
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
