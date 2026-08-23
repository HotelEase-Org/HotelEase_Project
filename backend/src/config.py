import os
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


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # --- S3 object storage (guest ID-document uploads) ---------------------
    # Bucket is private; the EC2 instance role grants s3:PutObject, so no keys
    # are stored anywhere. Region defaults to where the rest of the stack runs.
    S3_BUCKET = os.environ.get("S3_BUCKET", "hotelease-uploads")
    AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
    # Hard ceiling on any upload; Flask rejects larger bodies with 413.
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
