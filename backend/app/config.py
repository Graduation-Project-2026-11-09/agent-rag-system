import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app"
    )
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    MAIL_HOST = os.environ.get("MAIL_HOST", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))
