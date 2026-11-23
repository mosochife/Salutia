from datetime import datetime, timezone

from flask_login import UserMixin

from app import db


def utcnow():
    return datetime.now(timezone.utc)


class Organisation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sender_type = db.Column(db.String(50), nullable=False)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


class Contact(db.Model):
    __table_args__ = (db.UniqueConstraint("org_id", "email"),)

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=False)
    name = db.Column(db.String(120))
    email = db.Column(db.String(255), nullable=False)
    consented_at = db.Column(db.DateTime(timezone=True))
    opted_out_at = db.Column(db.DateTime(timezone=True))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    season = db.Column(db.String(50))
    status = db.Column(db.String(20), default="draft", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class SendLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("message.id"), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey("contact.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True))
    error = db.Column(db.Text)
