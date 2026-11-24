from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager.init_app(app)

    from app import models  # noqa: F401
    from app.auth import bp as auth_bp
    from app.compose import bp as messages_bp
    from app.contacts import bp as contacts_bp
    from app.messaging import ConsoleProvider

    app.extensions["message_provider"] = ConsoleProvider()
    app.register_blueprint(auth_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(messages_bp)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def home():
        return "Salutia is running"

    return app
