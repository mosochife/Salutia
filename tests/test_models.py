import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import Contact, Organisation
from config import Config


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


def make_orgs():
    a = Organisation(name="A", sender_type="school")
    b = Organisation(name="B", sender_type="hotel")
    db.session.add_all([a, b])
    db.session.commit()
    return a, b


def test_contacts_are_scoped_to_organisation(app):
    a, b = make_orgs()
    db.session.add(Contact(org_id=a.id, name="Ada", email="ada@example.com"))
    db.session.add(Contact(org_id=b.id, name="Bola", email="bola@example.com"))
    db.session.commit()

    emails = [c.email for c in Contact.query.filter_by(org_id=a.id)]
    assert emails == ["ada@example.com"]


def test_duplicate_email_in_same_org_is_rejected(app):
    a, _ = make_orgs()
    db.session.add(Contact(org_id=a.id, email="ada@example.com"))
    db.session.commit()

    db.session.add(Contact(org_id=a.id, email="ada@example.com"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_contact_needs_email_or_phone(app):
    a, _ = make_orgs()
    db.session.add(Contact(org_id=a.id, name="Nobody"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_phone_only_contacts_are_allowed(app):
    a, _ = make_orgs()
    db.session.add(Contact(org_id=a.id, name="Ada", phone="+2348012345678"))
    db.session.add(Contact(org_id=a.id, name="Bola", phone="+2348098765432"))
    db.session.commit()
    assert Contact.query.filter_by(org_id=a.id).count() == 2


def test_duplicate_phone_in_same_org_is_rejected(app):
    a, _ = make_orgs()
    db.session.add(Contact(org_id=a.id, phone="+2348012345678"))
    db.session.commit()

    db.session.add(Contact(org_id=a.id, phone="+2348012345678"))
    with pytest.raises(IntegrityError):
        db.session.commit()
