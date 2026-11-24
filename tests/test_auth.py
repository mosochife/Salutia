import pytest

from app import create_app, db
from app.models import Organisation, User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


SIGNUP = {
    "org_name": "Bright School",
    "sender_type": "school",
    "email": "head@example.com",
    "password": "correct-horse",
    "confirm": "correct-horse",
}


def signup(client, **overrides):
    return client.post("/signup", data={**SIGNUP, **overrides})


def test_signup_creates_org_and_hashed_user(app, client):
    assert signup(client).status_code == 302
    with app.app_context():
        user = User.query.filter_by(email="head@example.com").one()
        assert user.password_hash != "correct-horse"
        assert user.org_id == Organisation.query.one().id


def test_duplicate_email_is_rejected(app, client):
    signup(client)
    resp = signup(app.test_client(), org_name="Another")
    assert resp.status_code == 200
    with app.app_context():
        assert User.query.count() == 1
        assert Organisation.query.count() == 1


def test_short_password_is_rejected(app, client):
    resp = signup(client, password="short", confirm="short")
    assert resp.status_code == 200
    with app.app_context():
        assert User.query.count() == 0


def test_login_with_right_password(app, client):
    signup(client)
    other = app.test_client()
    resp = other.post(
        "/login", data={"email": "head@example.com", "password": "correct-horse"}
    )
    assert resp.status_code == 302
    assert other.get("/dashboard").status_code == 200


def test_login_with_wrong_password(app, client):
    signup(client)
    other = app.test_client()
    resp = other.post(
        "/login", data={"email": "head@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 200
    assert other.get("/dashboard").status_code == 302


def test_dashboard_requires_login(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_ends_the_session(app, client):
    signup(client)
    assert client.get("/dashboard").status_code == 200
    client.post("/logout")
    assert client.get("/dashboard").status_code == 302
