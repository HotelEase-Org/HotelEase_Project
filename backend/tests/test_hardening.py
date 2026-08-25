"""Tests for the post-pentest hardening batch.

Covers the application-layer fixes from deliverables/Security_Assessment.md:
booking caps (P-H1), session revalidation (P-M1), finite payment amounts
(P-M2), room-rate validation (P-M3), Maintenance-room booking block (P-M4),
and guest field validation (P-L2). All fixes are non-HTTPS.
"""

from datetime import date, timedelta

from src.extensions import db
from src.models import Staff, Room
from tests.conftest import login


def _payload(**overrides):
    data = {
        "full_name": "Kofi Test",
        "email": "kofi@example.com",
        "phone_number": "0200000000",
        "room_id": 1,
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-04",
    }
    data.update(overrides)
    return data


# --- P-H1: booking caps -----------------------------------------------------
def test_booking_rejects_overlong_stay(client):
    r = client.post("/api/bookings", json=_payload(
        check_in_date="2026-09-01", check_out_date="2026-12-15"))  # ~105 nights
    assert r.status_code == 400


def test_booking_rejects_far_future_checkin(client):
    check_in = (date.today() + timedelta(days=400)).isoformat()
    check_out = (date.today() + timedelta(days=402)).isoformat()
    r = client.post("/api/bookings", json=_payload(
        check_in_date=check_in, check_out_date=check_out))
    assert r.status_code == 400


def test_booking_within_limits_still_succeeds(client):
    assert client.post("/api/bookings", json=_payload()).status_code == 201


# --- P-L2: email format + whitespace-only fields ----------------------------
def test_booking_rejects_malformed_email(client):
    assert client.post("/api/bookings", json=_payload(email="not-an-email")).status_code == 400


def test_booking_rejects_whitespace_only_name(client):
    assert client.post("/api/bookings", json=_payload(full_name="   ")).status_code == 400


# --- P-M4: out-of-service rooms are not bookable ----------------------------
def test_maintenance_room_cannot_be_booked(client, app):
    with app.app_context():
        room = db.session.get(Room, 1)
        room.status = "Maintenance"
        db.session.commit()
    assert client.post("/api/bookings", json=_payload()).status_code == 409


# --- P-M2: payment must be a finite, positive number ------------------------
def _book_id(client):
    return client.post("/api/bookings", json=_payload()).get_json()["booking"]["booking_id"]


def test_payment_rejects_nan(client):
    bid = _book_id(client)
    login(client, "reception")
    r = client.post("/api/reception/payments",
                    json={"booking_id": bid, "amount": "nan", "payment_method": "Cash"})
    assert r.status_code == 400


def test_payment_rejects_infinity(client):
    bid = _book_id(client)
    login(client, "reception")
    r = client.post("/api/reception/payments",
                    json={"booking_id": bid, "amount": "Infinity", "payment_method": "Cash"})
    assert r.status_code == 400


def test_valid_payment_still_succeeds(client):
    bid = _book_id(client)
    login(client, "reception")
    r = client.post("/api/reception/payments",
                    json={"booking_id": bid, "amount": 150, "payment_method": "Cash"})
    assert r.status_code == 201


# --- P-M3: room rate validation ---------------------------------------------
def test_add_room_rejects_negative_rate(client):
    login(client, "manager")
    r = client.post("/api/manager/rooms",
                    json={"room_number": "301", "room_type": "Standard", "rate_per_night": -100})
    assert r.status_code == 400


def test_add_room_rejects_nonfinite_rate(client):
    login(client, "manager")
    r = client.post("/api/manager/rooms",
                    json={"room_number": "302", "room_type": "Standard", "rate_per_night": "Infinity"})
    assert r.status_code == 400


def test_add_room_accepts_valid_rate(client):
    login(client, "manager")
    r = client.post("/api/manager/rooms",
                    json={"room_number": "303", "room_type": "Standard", "rate_per_night": 250})
    assert r.status_code == 201


# --- P-M1: session is revalidated against the database ----------------------
def test_deleted_staff_session_is_rejected(client, app):
    login(client, "manager")
    # Sanity: a live session works.
    assert client.get("/api/manager/analytics").status_code == 200
    # The account is removed (e.g. the employee is let go) while the cookie lives.
    with app.app_context():
        db.session.delete(Staff.query.filter_by(username="manager").first())
        db.session.commit()
    # The stale cookie must no longer authorise anything.
    assert client.get("/api/manager/analytics").status_code == 401


def test_demoted_staff_loses_access_immediately(client, app):
    login(client, "manager")
    assert client.get("/api/manager/analytics").status_code == 200
    # Manager is demoted to receptionist while holding a manager cookie.
    with app.app_context():
        staff = Staff.query.filter_by(username="manager").first()
        staff.role = "receptionist"
        db.session.commit()
    # Authorisation now follows the database role, not the cookie's.
    assert client.get("/api/manager/analytics").status_code == 403
