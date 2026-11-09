from flask import Flask

from .config import Config
from .extensions import db, migrate


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes.health import bp as health_bp

    app.register_blueprint(health_bp, url_prefix="/api")
    return app
