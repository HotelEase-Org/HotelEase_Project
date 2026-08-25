from datetime import date
import re

from flask import Blueprint, request, jsonify

from ..extensions import db, limiter
from ..models import Guest, Room, Booking
from ..services.storage import upload_id_document, UploadError
from ..controllers.availability import (
    is_room_available,
    generate_reference,
    nights_between,
)

guest_bp = Blueprint("guest", __name__, url_prefix="/api")

# Bounds on a single public booking request. A Pending booking immediately holds
# the room, so without these one anonymous request could tie a room up for years
# (or for an absurd stay length) and deny it to real guests. These caps keep an
# unconfirmed hold within a sane range.
MAX_STAY_NIGHTS = 30
MAX_ADVANCE_DAYS = 365

# Pragmatic email shape check (not full RFC 5322): exactly one @, no whitespace,
# and a dot in the domain. Enough to reject typos and junk without rejecting
# valid-but-unusual addresses.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _parse_date(value):
    # Expects YYYY-MM-DD; raises ValueError if malformed.
    return date.fromisoformat(value)


@guest_bp.get("/rooms/available")
def available_rooms():
    """Public: list room types available for a date range."""
    try:
        check_in = _parse_date(request.args["check_in"])
        check_out = _parse_date(request.args["check_out"])
    except (KeyError, ValueError):
        return jsonify(error="check_in and check_out (YYYY-MM-DD) are required"), 400
    if check_out <= check_in:
        return jsonify(error="check_out must be after check_in"), 400

    rooms = Room.query.filter(Room.status != "Maintenance").all()
    # Return only what the public booking form needs. The full to_dict() also
    # exposes internal fields (assigned staff, last-cleaned, housekeeping status)
    # that guests should never see, so we trim the payload here.
    available = [
        {
            "room_id": r.room_id,
            "room_number": r.room_number,
            "room_type": r.room_type,
            "rate_per_night": float(r.rate_per_night),
        }
        for r in rooms
        if is_room_available(r.room_id, check_in, check_out)
    ]
    return jsonify(rooms=available)


@guest_bp.post("/bookings")
@limiter.limit("5 per hour; 20 per day")
def create_booking():
    """Public booking request. Accepts JSON or multipart/form-data.

    When sent as multipart with an "id_document" file, the file is streamed to
    the private S3 bucket and its object key is stored on the booking. The file
    is never written to local disk. Creates the guest if new; blocks double
    bookings.
    """
    # Read the fields uniformly whether the client sent JSON or a form.
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.form
        id_document = request.files.get("id_document")
    else:
        data = request.get_json(silent=True) or {}
        id_document = None

    required = ["full_name", "email", "phone_number", "room_id",
                "check_in_date", "check_out_date"]

    def _field(name):
        # Strip strings before the presence test so a whitespace-only value
        # ("   ") counts as missing rather than passing and collapsing to "".
        v = data.get(name)
        return v.strip() if isinstance(v, str) else v

    missing = [f for f in required if not _field(f)]
    if missing:
        return jsonify(error=f"Missing fields: {', '.join(missing)}"), 400

    if not _EMAIL_RE.match(_field("email") or ""):
        return jsonify(error="A valid email address is required"), 400

    # room_id arrives as an int in JSON but a string in a form; coerce safely.
    try:
        room_id = int(data.get("room_id"))
    except (TypeError, ValueError):
        return jsonify(error="A valid room_id is required"), 400

    try:
        check_in = _parse_date(data["check_in_date"])
        check_out = _parse_date(data["check_out_date"])
    except (KeyError, ValueError):
        return jsonify(error="Dates must be in YYYY-MM-DD format"), 400
    if check_out <= check_in:
        return jsonify(error="check_out must be after check_in"), 400
    if check_in < date.today():
        return jsonify(error="Check-in date cannot be in the past"), 400
    if nights_between(check_in, check_out) > MAX_STAY_NIGHTS:
        return jsonify(error=f"A booking cannot exceed {MAX_STAY_NIGHTS} nights"), 400
    if (check_in - date.today()).days > MAX_ADVANCE_DAYS:
        return jsonify(error="Check-in date is too far in the future"), 400

    room = db.session.get(Room, room_id)
    if room is None:
        return jsonify(error="Room not found"), 404

    # Out-of-service rooms are hidden from the public listing; enforce the same
    # rule on the create path so a guessed/sequential room_id cannot book a room
    # that was deliberately withheld. Same generic 409 as an unavailable room so
    # room status is not disclosed to the caller.
    if room.status == "Maintenance":
        return jsonify(error="Room is not available for those dates"), 409

    if not is_room_available(room.room_id, check_in, check_out):
        return jsonify(error="Room is not available for those dates"), 409

    # Validate and stream the ID document to S3 BEFORE writing the booking, so a
    # bad upload fails cleanly instead of leaving a half-created record.
    id_document_key = None
    if id_document is not None and id_document.filename:
        try:
            id_document_key = upload_id_document(id_document)
        except UploadError as e:
            return jsonify(error=str(e)), 400

    # Reuse an existing guest by email, otherwise create one.
    guest = Guest.query.filter_by(email=data["email"].strip()).first()
    if guest is None:
        guest = Guest(
            full_name=data["full_name"].strip(),
            email=data["email"].strip(),
            phone_number=data["phone_number"].strip(),
            id_number=(data.get("id_number") or "").strip() or None,
        )
        db.session.add(guest)
        db.session.flush()  # assign guest_id before booking insert

    nights = nights_between(check_in, check_out)
    cost_total = float(room.rate_per_night) * nights

    booking = Booking(
        reference=generate_reference(),
        guest_id=guest.guest_id,
        room_id=room.room_id,
        check_in_date=check_in,
        check_out_date=check_out,
        booking_status="Pending",
        payment_status="Unpaid",
        cost_total=cost_total,
        id_document_key=id_document_key,
    )
    db.session.add(booking)
    db.session.commit()

    return jsonify(
        message="Booking request received",
        reference=booking.reference,
        booking=booking.to_dict(),
    ), 201


@guest_bp.get("/bookings/lookup")
def lookup_booking():
    """Public status check by reference plus email (light verification)."""
    reference = (request.args.get("reference") or "").strip().upper()
    email = (request.args.get("email") or "").strip()
    if not reference or not email:
        return jsonify(error="reference and email are required"), 400

    booking = Booking.query.filter_by(reference=reference).first()
    if booking is None or booking.guest.email.lower() != email.lower():
        return jsonify(error="No matching booking found"), 404

    result = booking.to_dict()
    result["guest_name"] = booking.guest.full_name
    result["room_number"] = booking.room.room_number
    result["room_type"] = booking.room.room_type
    return jsonify(booking=result)
