import pytest

from src import create_app
from src.extensions import db
from src.models import Room, Staff


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = "*"


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        # One available room and one account per role.
        db.session.add(Room(room_number="201", room_type="Deluxe",
                            rate_per_night=400, status="Available"))
        for name, role, username in [
            ("Manager", "manager", "manager"),
            ("Recep", "receptionist", "reception"),
            ("Cleaner", "housekeeping", "housekeeping"),
        ]:
            s = Staff(full_name=name, role=role, username=username)
            s.set_password("pw")
            db.session.add(s)
        db.session.commit()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password="pw"):
    return client.post("/api/auth/login",
                       json={"username": username, "password": password})
