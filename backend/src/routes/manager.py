from collections import defaultdict

from flask import Blueprint, request, jsonify

from ..extensions import db
from ..models import Room, Booking, Payment, Staff
from ..middleware import role_required

manager_bp = Blueprint("manager", __name__, url_prefix="/api/manager")


@manager_bp.get("/analytics")
@role_required("manager")
def analytics():
    total_rooms = Room.query.count()
    occupied = Room.query.filter_by(status="Occupied").count()
    occupancy_rate = round((occupied / total_rooms) * 100, 1) if total_rooms else 0.0
    total_bookings = Booking.query.count()
    total_revenue = sum(float(p.amount) for p in Payment.query.all())

    # Revenue grouped by year-month, for the trend chart.
    by_month = defaultdict(float)
    for p in Payment.query.all():
        key = p.payment_date.strftime("%Y-%m")
        by_month[key] += float(p.amount)
    revenue_trend = [
        {"month": k, "revenue": round(v, 2)} for k, v in sorted(by_month.items())
    ]

    # Bookings grouped by room type, for the donut.
    by_type = defaultdict(int)
    for b in Booking.query.all():
        by_type[b.room.room_type] += 1
    bookings_by_type = [{"room_type": k, "count": v} for k, v in by_type.items()]

    return jsonify(
        total_revenue=round(total_revenue, 2),
        occupancy_rate=occupancy_rate,
        total_bookings=total_bookings,
        revenue_trend=revenue_trend,
        bookings_by_type=bookings_by_type,
    )


@manager_bp.get("/staff")
@role_required("manager")
def list_staff():
    return jsonify(staff=[s.to_dict() for s in Staff.query.all()])


@manager_bp.post("/staff")
@role_required("manager")
def create_staff():
    data = request.get_json(silent=True) or {}
    required = ["full_name", "role", "username", "password"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify(error=f"Missing fields: {', '.join(missing)}"), 400
    if data["role"] not in ("receptionist", "housekeeping", "manager"):
        return jsonify(error="Invalid role"), 400
    if Staff.query.filter_by(username=data["username"].strip()).first():
        return jsonify(error="Username already exists"), 409

    staff = Staff(
        full_name=data["full_name"].strip(),
        role=data["role"],
        username=data["username"].strip(),
    )
    staff.set_password(data["password"])
    db.session.add(staff)
    db.session.commit()
    return jsonify(message="Staff account created", staff=staff.to_dict()), 201


@manager_bp.get("/rooms")
@role_required("manager")
def inventory():
    rooms = Room.query.order_by(Room.room_number).all()
    return jsonify(rooms=[r.to_dict() for r in rooms])


@manager_bp.post("/rooms")
@role_required("manager")
def add_room():
    data = request.get_json(silent=True) or {}
    required = ["room_number", "room_type", "rate_per_night"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify(error=f"Missing fields: {', '.join(missing)}"), 400
    if Room.query.filter_by(room_number=str(data["room_number"]).strip()).first():
        return jsonify(error="Room number already exists"), 409

    room = Room(
        room_number=str(data["room_number"]).strip(),
        room_type=data["room_type"].strip(),
        rate_per_night=data["rate_per_night"],
        status="Available",
    )
    db.session.add(room)
    db.session.commit()
    return jsonify(message="Room added", room=room.to_dict()), 201
