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
    from .routes.health import bp as health_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
    register_cli(app)
    return app
