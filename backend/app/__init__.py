from flask import Flask

from .config import Config
from .extensions import db, migrate


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401  マイグレーションの自動生成でモデルを検出させる
    from .cli import register_cli
    from .routes.auth import bp as auth_bp
    from .routes.chat import bp as chat_bp
    from .routes.documents import bp as documents_bp
    from .routes.health import bp as health_bp
    from .routes.inquiries import bp as inquiries_bp
    from .routes.logs import bp as logs_bp
    from .routes.notices import bp as notices_bp
    from .routes.users import bp as users_bp

    for blueprint in (
        health_bp,
        auth_bp,
        chat_bp,
        documents_bp,
        inquiries_bp,
        logs_bp,
        notices_bp,
        users_bp,
    ):
        app.register_blueprint(blueprint, url_prefix="/api")
    register_cli(app)
    return app
