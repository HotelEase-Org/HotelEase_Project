from dotenv import load_dotenv

# Load .env before Config is imported so env vars are available at class build.
load_dotenv()

from flask import Flask, jsonify  # noqa: E402
from flask_cors import CORS  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from .config import Config  # noqa: E402
from .extensions import db, limiter  # noqa: E402


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Behind nginx, the real client IP arrives in X-Forwarded-For (nginx appends
    # the true remote_addr, so the right-most hop is trustworthy). Without this,
    # Flask sees every request as 127.0.0.1 and per-IP rate limits collapse into
    # one shared bucket. x_for=1 trusts exactly one proxy hop; x_proto lets
    # request.is_secure reflect TLS once HTTPS is terminated at nginx.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    limiter.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

    # Import models so SQLAlchemy registers the tables, then wire up routes.
    from . import models  # noqa: F401
    from .routes import register_blueprints

    register_blueprints(app)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="hotelease-api")

    @app.errorhandler(429)
    def ratelimited(e):
        # Keep the shape the frontend expects ({error: ...}) instead of the
        # default HTML page, so the login form shows a clean message.
        return jsonify(error="Too many attempts. Please wait a minute and try again."), 429

    with app.app_context():
        db.create_all()

    return app
