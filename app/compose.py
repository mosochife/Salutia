from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length

from app import db
from app.messaging import CHANNELS, analyze_sms, send_batch, skip_reason
from app.models import Contact, Message, SendLog

bp = Blueprint("messages", __name__, url_prefix="/messages")


class MessageForm(FlaskForm):
    subject = StringField("Subject", validators=[DataRequired(), Length(max=200)])
    body = TextAreaField("Message", validators=[DataRequired(), Length(max=2000)])
    season = StringField("Season (optional)", validators=[Length(max=50)])


class SendForm(FlaskForm):
    channel = SelectField("Send by", choices=[("email", "Email"), ("sms", "SMS")])


def own_message_or_404(message_id):
    return Message.query.filter_by(
        id=message_id, org_id=current_user.org_id
    ).first_or_404()


def own_contacts():
    return (
        Contact.query.filter_by(org_id=current_user.org_id)
        .order_by(Contact.id)
        .all()
    )


@bp.route("/")
@login_required
def index():
    messages = (
        Message.query.filter_by(org_id=current_user.org_id)
        .order_by(Message.id.desc())
        .all()
    )
    return render_template("messages.html", messages=messages)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(
            org_id=current_user.org_id,
            subject=form.subject.data.strip(),
            body=form.body.data.strip(),
            season=(form.season.data or "").strip() or None,
        )
        db.session.add(message)
        db.session.commit()
        return redirect(url_for("messages.detail", message_id=message.id))
    return render_template("form.html", form=form, title="New message")


@bp.route("/<int:message_id>")
@login_required
def detail(message_id):
    message = own_message_or_404(message_id)
    contacts = own_contacts()
    preview = {}
    for channel in CHANNELS:
        eligible = sum(1 for c in contacts if skip_reason(channel, c) is None)
        preview[channel] = {
            "eligible": eligible,
            "skipped": len(contacts) - eligible,
        }
    history = (
        db.session.query(
            SendLog.channel, SendLog.status, db.func.count(SendLog.id).label("n")
        )
        .filter(SendLog.message_id == message.id)
        .group_by(SendLog.channel, SendLog.status)
        .all()
    )
    return render_template(
        "message_detail.html",
        message=message,
        preview=preview,
        history=history,
        sms_info=analyze_sms(message.body),
        form=SendForm(),
    )


@bp.route("/<int:message_id>/send", methods=["POST"])
@login_required
def send(message_id):
    message = own_message_or_404(message_id)
    form = SendForm()
    if form.validate_on_submit():
        provider = current_app.extensions["message_provider"]
        counts = send_batch(message, own_contacts(), form.channel.data, provider)
        flash(
            f"Sent {counts['sent']}, skipped {counts['skipped']}, "
            f"failed {counts['failed']}, already sent {counts['already_sent']}."
        )
    return redirect(url_for("messages.detail", message_id=message.id))
