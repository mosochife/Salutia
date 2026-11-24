import pytest

from app import create_app, db
from app.models import Contact
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


def signup(client, org, email):
    client.post(
        "/signup",
        data={
            "org_name": org,
            "sender_type": "school",
            "email": email,
            "password": "correct-horse",
            "confirm": "correct-horse",
        },
    )
    return client


@pytest.fixture
def school(app):
    return signup(app.test_client(), "School A", "a@example.com")


@pytest.fixture
def hotel(app):
    return signup(app.test_client(), "Hotel B", "b@example.com")


def add(client, **fields):
    return client.post("/contacts/", data={"consent": "y", **fields})


def count(app):
    with app.app_context():
        return Contact.query.count()


def test_contacts_page_requires_login(app):
    resp = app.test_client().get("/contacts/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_email_contact_records_email_consent_only(app, school):
    assert add(school, name="Ada", email="Ada@Example.com").status_code == 302
    with app.app_context():
        c = Contact.query.one()
        assert c.email == "ada@example.com"
        assert c.phone is None
        assert c.email_consented_at is not None
        assert c.sms_consented_at is None


def test_phone_only_contact_is_cleaned_and_consented(app, school):
    add(school, phone="+234 801 234 5678")
    with app.app_context():
        c = Contact.query.one()
        assert c.phone == "+2348012345678"
        assert c.email is None
        assert c.sms_consented_at is not None
        assert c.email_consented_at is None


def test_consent_checkbox_is_required(app, school):
    resp = school.post("/contacts/", data={"email": "x@example.com"})
    assert resp.status_code == 200
    assert count(app) == 0


def test_email_or_phone_is_required(app, school):
    assert add(school, name="Nobody").status_code == 200
    assert count(app) == 0


def test_invalid_phone_is_rejected(app, school):
    assert add(school, phone="abc").status_code == 200
    assert count(app) == 0


def test_two_phone_only_contacts_do_not_clash(app, school):
    add(school, phone="+2348012345678")
    add(school, phone="+2348098765432")
    assert count(app) == 2


def test_duplicate_email_in_same_org_is_rejected(app, school):
    add(school, email="ada@example.com")
    add(school, email="ada@example.com")
    assert count(app) == 1


def test_same_email_is_allowed_in_different_orgs(app, school, hotel):
    add(school, email="ada@example.com")
    add(hotel, email="ada@example.com")
    assert count(app) == 2


def test_org_sees_only_its_own_contacts(app, school, hotel):
    add(school, email="ada@example.com")
    add(hotel, email="bola@example.com")
    page = school.get("/contacts/").get_data(as_text=True)
    assert "ada@example.com" in page
    assert "bola@example.com" not in page


def test_cannot_delete_another_orgs_contact(app, school, hotel):
    add(school, email="ada@example.com")
    with app.app_context():
        contact_id = Contact.query.one().id
    assert hotel.post(f"/contacts/{contact_id}/delete").status_code == 404
    assert count(app) == 1


def test_can_delete_own_contact(app, school):
    add(school, email="ada@example.com")
    with app.app_context():
        contact_id = Contact.query.one().id
    school.post(f"/contacts/{contact_id}/delete")
    assert count(app) == 0


def test_csv_upload_normalizes_nigerian_numbers_and_skips_duplicates(client):
    import io

    # Log in using the existing fixture's user or create one
    from app import db
    from app.models import Contact, Organisation, User
    from werkzeug.security import generate_password_hash

    with client.application.app_context():
        org = Organisation(name="Benue Royal Suites", sender_type="hotel")
        db.session.add(org)
        db.session.flush()
        user = User(
            org_id=org.id,
            email="manager@hotel.ng",
            password_hash=generate_password_hash("secret123"),
        )
        db.session.add(user)
        db.session.commit()

    client.post("/login", data={"email": "manager@hotel.ng", "password": "secret123"})

    csv_data = (
        "name,email,phone\n"
        "Mrs. Ochanya,,08031234567\n"
        "Duplicate Phone,,+2348031234567\n"
        "Mr. Tunde,tunde@example.com,\n"
        "Invalid Row,,not-a-phone\n"
    )
    resp = client.post(
        "/contacts/upload",
        data={
            "csv_file": (io.BytesIO(csv_data.encode("utf-8")), "parents.csv"),
            "consent": "y",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"2 added, 1 duplicates skipped, 1 invalid rows skipped." in resp.data
    assert b"+2348031234567" in resp.data
