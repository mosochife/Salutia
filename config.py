import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///salutia.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Optional live providers (falls back to ConsoleProvider if unset)
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")
    BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "Salutia")

    TERMII_API_KEY = os.environ.get("TERMII_API_KEY", "")
    TERMII_SENDER_ID = os.environ.get("TERMII_SENDER_ID", "Salutia")
    TERMII_CHANNEL = os.environ.get("TERMII_CHANNEL", "dnd")
