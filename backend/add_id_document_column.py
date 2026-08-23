"""One-off: add the bookings.id_document_key column to an existing database.

Why this exists: the project builds its schema with db.create_all(), which
creates any MISSING tables but does not ALTER tables that already exist. So:

  - Fresh databases (the test suite, a local SQLite file, or a re-seeded RDS)
    get the new column automatically from the model -- nothing to run here.
  - A live database that already has a "bookings" table with data you want to
    keep needs the column added once. That is what this script does.

It is idempotent: run it as many times as you like; it only acts if the column
is missing. Works on both PostgreSQL (RDS) and SQLite.

Usage (from backend/, with the venv active and .env pointing at the database):
    python add_id_document_column.py
"""
from sqlalchemy import inspect, text

from src import create_app
from src.extensions import db

app = create_app()

with app.app_context():
    columns = [c["name"] for c in inspect(db.engine).get_columns("bookings")]
    if "id_document_key" in columns:
        print("Column bookings.id_document_key already present -- nothing to do.")
    else:
        db.session.execute(
            text("ALTER TABLE bookings ADD COLUMN id_document_key VARCHAR(255)")
        )
        db.session.commit()
        print("Added column bookings.id_document_key.")
