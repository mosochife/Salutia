import csv
import io
import re

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from sqlalchemy.exc import IntegrityError
from wtforms import BooleanField, StringField
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    Optional,
    ValidationError,
)

from app import db
from app.models import Contact, utcnow

bp = Blueprint("contacts", __name__, url_prefix="/contacts")

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def clean_phone(value):
    return re.sub(r"[\s\-()]", "", value or "")


def normalize_ng_phone(value):
    """Convert Nigerian local formats (080..., 23480...) to +23480..."""
    phone = clean_phone(value)
    if not phone:
        return None
    if re.fullmatch(r"^0[789][01]\d{8}$", phone):
        return "+234" + phone[1:]
    if re.fullmatch(r"^234[789][01]\d{8}$", phone):
        return "+" + phone
    return phone


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[Optional(), Length(max=120)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=255)])
    phone = StringField(
        "Phone (with country code)", validators=[Optional(), Length(max=30)]
    )
    consent = BooleanField(
        "This person agreed to receive greetings from us",
        validators=[DataRequired(message="Consent is required to add a contact.")],
    )

    def validate_phone(self, field):
        phone = normalize_ng_phone(field.data)
        if phone and not PHONE_RE.match(phone):
            raise ValidationError(
                "Enter a valid phone number, for example +2348012345678 or 08012345678."
            )


class CsvUploadForm(FlaskForm):
    csv_file = FileField(
        "CSV File (columns: name, email, phone)",
        validators=[
            FileRequired(message="Choose a CSV file to upload."),
            FileAllowed(["csv"], "Only .csv files are allowed."),
        ],
    )
    consent = BooleanField(
        "All contacts in this file agreed to receive greetings from us",
        validators=[DataRequired(message="Consent confirmation is required.")],
    )


class DeleteForm(FlaskForm):
    pass


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    form = ContactForm()
    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower() or None
        phone = normalize_ng_phone(form.phone.data)
        if not email and not phone:
            flash("Add an email or a phone number.")
        else:
            now = utcnow()
            db.session.add(
                Contact(
                    org_id=current_user.org_id,
                    name=(form.name.data or "").strip() or None,
                    email=email,
                    phone=phone,
                    email_consented_at=now if email else None,
                    sms_consented_at=now if phone else None,
                )
            )
            try:
                db.session.commit()
                return redirect(url_for("contacts.index"))
            except IntegrityError:
                db.session.rollback()
                flash("That email or phone number is already in your list.")
    contacts = (
        Contact.query.filter_by(org_id=current_user.org_id).order_by(Contact.id).all()
    )
    return render_template(
        "contacts.html", form=form, contacts=contacts, delete_form=DeleteForm()
    )


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = CsvUploadForm()
    if form.validate_on_submit():
        raw = form.csv_file.data.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(raw))
        added = skipped = duplicates = 0
        now = utcnow()

        for row in reader:
            norm = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            name = norm.get("name") or None
            email = (norm.get("email") or "").lower() or None
            phone = normalize_ng_phone(norm.get("phone"))

            if email and "@" not in email:
                email = None
            if phone and not PHONE_RE.match(phone):
                phone = None
            if not email and not phone:
                skipped += 1
                continue

            db.session.add(
                Contact(
                    org_id=current_user.org_id,
                    name=name,
                    email=email,
                    phone=phone,
                    email_consented_at=now if email else None,
                    sms_consented_at=now if phone else None,
                )
            )
            try:
                db.session.commit()
                added += 1
            except IntegrityError:
                db.session.rollback()
                duplicates += 1

        flash(
            f"CSV import complete: {added} added, {duplicates} duplicates skipped, {skipped} invalid rows skipped."
        )
        return redirect(url_for("contacts.index"))
    return render_template("upload_contacts.html", form=form)


@bp.route("/<int:contact_id>/delete", methods=["POST"])
@login_required
def delete(contact_id):
    contact = Contact.query.filter_by(
        id=contact_id, org_id=current_user.org_id
    ).first_or_404()
    if DeleteForm().validate_on_submit():
        db.session.delete(contact)
        db.session.commit()
    return redirect(url_for("contacts.index"))
