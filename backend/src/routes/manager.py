from collections import defaultdict

from flask import Blueprint, request, jsonify, session

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


@manager_bp.patch("/staff/<int:staff_id>")
@role_required("manager")
def update_staff(staff_id):
    """Edit a staff member: rename, change role, or reset password.

    Username is intentionally immutable here to keep logins stable.
    """
    data = request.get_json(silent=True) or {}
    staff = db.get_or_404(Staff, staff_id)

    new_role = data.get("role")
    if new_role is not None:
        if new_role not in ("receptionist", "housekeeping", "manager"):
            return jsonify(error="Invalid role"), 400
        # Do not strand the account set without a manager.
        if staff.role == "manager" and new_role != "manager":
            managers = Staff.query.filter_by(role="manager").count()
            if managers <= 1:
                return jsonify(error="Cannot change the role of the only manager"), 409
        staff.role = new_role

    if data.get("full_name"):
        staff.full_name = data["full_name"].strip()
    if data.get("password"):
        staff.set_password(data["password"])

    db.session.commit()
    return jsonify(message="Staff account updated", staff=staff.to_dict())


@manager_bp.delete("/staff/<int:staff_id>")
@role_required("manager")
def delete_staff(staff_id):
    staff = db.get_or_404(Staff, staff_id)
    # A manager cannot delete their own logged-in account.
    if staff.staff_id == session.get("staff_id"):
        return jsonify(error="You cannot delete your own account"), 409
    # Never remove the last manager.
    if staff.role == "manager" and Staff.query.filter_by(role="manager").count() <= 1:
        return jsonify(error="Cannot delete the only manager"), 409
    db.session.delete(staff)
    db.session.commit()
    return jsonify(message="Staff account deleted")


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


@manager_bp.patch("/rooms/<int:room_id>")
@role_required("manager")
def update_room(room_id):
    """Edit a room: number, type, nightly rate, or status."""
    data = request.get_json(silent=True) or {}
    room = db.get_or_404(Room, room_id)

    if data.get("room_number"):
        new_number = str(data["room_number"]).strip()
        clash = Room.query.filter_by(room_number=new_number).first()
        if clash and clash.room_id != room.room_id:
            return jsonify(error="Room number already exists"), 409
        room.room_number = new_number
    if data.get("room_type"):
        room.room_type = data["room_type"].strip()
    if data.get("rate_per_night") is not None:
        try:
            rate = float(data["rate_per_night"])
        except (TypeError, ValueError):
            return jsonify(error="rate_per_night must be a number"), 400
        if rate <= 0:
            return jsonify(error="rate_per_night must be greater than zero"), 400
        room.rate_per_night = rate
    if data.get("status"):
        valid = {"Available", "Cleaning", "InProgress", "Occupied", "Maintenance"}
        if data["status"] not in valid:
            return jsonify(error=f"status must be one of {sorted(valid)}"), 400
        room.status = data["status"]

    db.session.commit()
    return jsonify(message="Room updated", room=room.to_dict())


@manager_bp.delete("/rooms/<int:room_id>")
@role_required("manager")
def delete_room(room_id):
    room = db.get_or_404(Room, room_id)
    # Refuse to delete a room that bookings still point at -- deleting it would
    # orphan those records (room_id is required and there is no cascade).
    linked = Booking.query.filter_by(room_id=room.room_id).count()
    if linked:
        return jsonify(
            error=f"Cannot delete a room with {linked} booking(s). "
                  "Set it to Maintenance instead."
        ), 409
    db.session.delete(room)
    db.session.commit()
    return jsonify(message="Room deleted")
