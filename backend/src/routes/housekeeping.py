from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, session

from ..extensions import db
from ..models import Room, Staff
from ..middleware import role_required

housekeeping_bp = Blueprint("housekeeping", __name__, url_prefix="/api/housekeeping")

HOUSE = ("housekeeping", "manager")


@housekeeping_bp.get("/rooms")
@role_required(*HOUSE)
def my_rooms():
    """Rooms that need attention, or are assigned to the logged-in cleaner."""
    staff = db.session.get(Staff, session["staff_id"])
    rooms = (
        Room.query.filter(Room.status.in_(("Cleaning", "Maintenance")))
        .order_by(Room.room_number)
        .all()
    )
    payload = []
    for r in rooms:
        d = r.to_dict()
        d["assigned_to_me"] = bool(
            r.assigned_staff and staff and r.assigned_staff == staff.full_name
        )
        payload.append(d)
    return jsonify(rooms=payload)


@housekeeping_bp.post("/rooms/<int:room_id>/status")
@role_required(*HOUSE)
def update_status(room_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    valid = {"Available", "Cleaning", "Occupied", "Maintenance"}
    if new_status not in valid:
        return jsonify(error=f"status must be one of {sorted(valid)}"), 400

    room = db.get_or_404(Room, room_id)
    room.status = new_status
    if new_status == "Available":
        room.last_cleaned = datetime.now(timezone.utc)
        room.assigned_staff = None
    db.session.commit()
    return jsonify(message="Room status updated", room=room.to_dict())


@housekeeping_bp.post("/rooms/<int:room_id>/flag-maintenance")
@role_required(*HOUSE)
def flag_maintenance(room_id):
    room = db.get_or_404(Room, room_id)
    room.status = "Maintenance"
    db.session.commit()
    return jsonify(message="Room flagged for maintenance", room=room.to_dict())
