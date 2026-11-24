from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required, login_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from app import db
from app.models import Organisation, User

bp = Blueprint("auth", __name__)

SENDER_TYPES = [("school", "School"), ("hotel", "Hotel"), ("other", "Other")]


class SignupForm(FlaskForm):
    org_name = StringField(
        "Organisation name", validators=[DataRequired(), Length(max=120)]
    )
    sender_type = SelectField("Type", choices=SENDER_TYPES)
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password")]
    )


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class LogoutForm(FlaskForm):
    pass


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("That email is already registered.")
        else:
            org = Organisation(
                name=form.org_name.data.strip(), sender_type=form.sender_type.data
            )
            db.session.add(org)
            db.session.flush()
            user = User(
                org_id=org.id,
                email=email,
                password_hash=generate_password_hash(form.password.data),
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("auth.dashboard"))
    return render_template("form.html", form=form, title="Create your account")


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(url_for("auth.dashboard"))
        flash("Wrong email or password.")
    return render_template("form.html", form=form, title="Log in")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if LogoutForm().validate_on_submit():
        logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", form=LogoutForm())
