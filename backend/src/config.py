import os
from datetime import timedelta
from pathlib import Path

# backend/ -- one level up from src/
BASE_DIR = Path(__file__).resolve().parent.parent


def _database_uri():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # SQLAlchemy needs the postgresql:// scheme, not the older postgres://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    # Local development fallback: SQLite inside the Flask instance folder.
    instance = BASE_DIR / "instance"
    instance.mkdir(exist_ok=True)
    return f"sqlite:///{instance / 'hotelease.db'}"


def _cors_origins():
    """Explicit cross-origin allowlist.

    We send cookies with every request (credentialed CORS), so a wildcard "*"
    origin is BOTH insecure and illegal in that mode -- it makes Flask-CORS
    reflect any attacker's Origin. We therefore never allow "*": production is
    same-origin (nginx serves the frontend and /api on one host, so no CORS is
    exercised), and only local development is cross-origin. Set CORS_ORIGINS to a
    comma-separated list to override the safe localhost defaults.
    """
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
    else:
        origins = [
            "http://localhost:8080", "http://127.0.0.1:8080",
            "http://localhost:5500", "http://127.0.0.1:5500",
        ]
    # Drop any wildcard: it cannot be combined with credentialed requests.
    return [o for o in origins if o != "*"]


def _truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = _cors_origins()

    # --- Session cookie hardening -----------------------------------------
    # HttpOnly keeps JS from reading the cookie; SameSite=Lax blocks it from
    # riding along on cross-site requests (CSRF defence). Secure is gated on
    # HTTPS being live -- turning it on over plain HTTP would stop the cookie
    # being sent at all and break login, so it defaults off until TLS is set up
    # (then set SESSION_COOKIE_SECURE=1 in the environment).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _truthy(os.environ.get("SESSION_COOKIE_SECURE", ""))
    # Idle logout: sessions are marked permanent at login, so this window bounds
    # how long an abandoned front-desk terminal stays signed in. Flask refreshes
    # the countdown on each request, making it an inactivity timeout, not a hard
    # cap on a working session.
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # --- S3 object storage (guest ID-document uploads) ---------------------
    # Bucket is private; the EC2 instance role grants s3:PutObject, so no keys
    # are stored anywhere. Region defaults to where the rest of the stack runs.
    S3_BUCKET = os.environ.get("S3_BUCKET", "hotelease-uploads")
    AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
    # Hard ceiling on any upload; Flask rejects larger bodies with 413.
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
