"""Seed the database with demo rooms and one staff account per role.

Usage (from backend/, with venv active):
    python seed.py
"""
from datetime import date, datetime, timedelta, timezone

from src import create_app
from src.extensions import db
from src.models import Guest, Room, Booking, Payment, Staff
from src.controllers.availability import generate_reference

app = create_app()

STAFF = [
    ("Abena Osei", "manager", "manager", "manager123"),
    ("Kofi Mensah", "receptionist", "reception", "reception123"),
    ("Kwame Asante", "housekeeping", "housekeeping", "cleaning123"),
]

ROOMS = [
    ("101", "Standard", 250, "Available"),
    ("102", "Standard", 250, "Occupied"),
    ("103", "Standard", 250, "Cleaning"),
    ("201", "Deluxe", 400, "Available"),
    ("202", "Deluxe", 400, "Available"),
    ("301", "Suite", 650, "Maintenance"),
]


def run():
    with app.app_context():
        db.drop_all()
        db.create_all()

        for full_name, role, username, password in STAFF:
            s = Staff(full_name=full_name, role=role, username=username)
            s.set_password(password)
            db.session.add(s)

        rooms = []
        for number, rtype, rate, status in ROOMS:
            r = Room(room_number=number, room_type=rtype,
                     rate_per_night=rate, status=status)
            rooms.append(r)
            db.session.add(r)
        db.session.flush()

        guest = Guest(full_name="Ama Boateng", email="ama@example.com",
                      phone_number="0244000000", id_number="GHA-123456789")
        db.session.add(guest)
        db.session.flush()

        check_in = date.today() + timedelta(days=2)
        check_out = check_in + timedelta(days=3)
        nights = (check_out - check_in).days
        booking = Booking(
            reference=generate_reference(),
            guest_id=guest.guest_id,
            room_id=rooms[0].room_id,
            check_in_date=check_in,
            check_out_date=check_out,
            booking_status="Confirmed",
            payment_status="Partial",
            cost_total=float(rooms[0].rate_per_night) * nights,
        )
        db.session.add(booking)
        db.session.flush()

        db.session.add(Payment(booking_id=booking.booking_id, amount=250,
                               payment_method="Mobile Money",
                               payment_date=datetime.now(timezone.utc)))

        db.session.commit()

        print("Seed complete.")
        print(f"  Staff accounts: {len(STAFF)} (see logins below)")
        for full_name, role, username, password in STAFF:
            print(f"    {role:13s} -> {username} / {password}")
        print(f"  Rooms: {len(ROOMS)}")
        print(f"  Demo booking reference: {booking.reference} (email {guest.email})")


if __name__ == "__main__":
    run()
