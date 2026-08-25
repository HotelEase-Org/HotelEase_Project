from datetime import date, datetime, timezone

from flask import Blueprint, request, jsonify, session
from sqlalchemy import or_

from ..extensions import db
from ..models import Booking, Room, Payment, Staff, Guest, DeletionRequest
from ..middleware import role_required

reception_bp = Blueprint("reception", __name__, url_prefix="/api/reception")

# Receptionists and managers can both use the front desk.
FRONT_DESK = ("receptionist", "manager")


@reception_bp.get("/dashboard")
@role_required(*FRONT_DESK)
def dashboard():
    today = date.today()
    arrivals = Booking.query.filter_by(check_in_date=today).count()
    departures = Booking.query.filter_by(check_out_date=today).count()
    occupied = Room.query.filter_by(status="Occupied").count()
    awaiting = Room.query.filter_by(status="Cleaning").count()
    return jsonify(
        arrivals_today=arrivals,
        departures_today=departures,
        rooms_occupied=occupied,
        awaiting_cleaning=awaiting,
    )


@reception_bp.get("/arrivals")
@role_required(*FRONT_DESK)
def arrivals():
    today = date.today()
    rows = (
        Booking.query.filter(
            (Booking.check_in_date == today) | (Booking.check_out_date == today)
        )
        .order_by(Booking.check_in_date)
        .all()
    )
    out = []
    for b in rows:
        d = b.to_dict()
        d["guest_name"] = b.guest.full_name
        d["room_number"] = b.room.room_number
        out.append(d)
    return jsonify(bookings=out)


@reception_bp.post("/bookings/<int:booking_id>/check-in")
@role_required(*FRONT_DESK)
def check_in(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    booking.booking_status = "CheckedIn"
    booking.room.status = "Occupied"
    db.session.commit()
    return jsonify(message="Guest checked in", booking=booking.to_dict())


@reception_bp.post("/bookings/<int:booking_id>/check-out")
@role_required(*FRONT_DESK)
def check_out(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    booking.booking_status = "CheckedOut"
    # Room needs cleaning before it is available again.
    booking.room.status = "Cleaning"
    db.session.commit()
    return jsonify(message="Guest checked out", booking=booking.to_dict())


@reception_bp.post("/payments")
@role_required(*FRONT_DESK)
def record_payment():
    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    amount = data.get("amount")
    method = (data.get("payment_method") or "").strip()
    if not booking_id or amount is None or not method:
        return jsonify(error="booking_id, amount and payment_method are required"), 400

    # Reject non-numeric or non-positive amounts: a payment must add value, so
    # zero and negatives (which would fake an unauthorised refund) are refused.
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        return jsonify(error="Amount must be a number"), 400
    if amount <= 0:
        return jsonify(error="Amount must be greater than zero"), 400

    booking = db.get_or_404(Booking, booking_id)
    payment = Payment(
        booking_id=booking.booking_id,
        amount=amount,
        payment_method=method,
        payment_date=datetime.now(timezone.utc),
    )
    db.session.add(payment)

    # Mark paid once total payments cover the booking cost.
    paid = sum(float(p.amount) for p in booking.payments) + amount
    booking.payment_status = "Paid" if paid >= float(booking.cost_total) else "Partial"
    db.session.commit()

    return jsonify(
        message="Payment recorded",
        payment=payment.to_dict(),
        payment_status=booking.payment_status,
    ), 201


@reception_bp.get("/rooms")
@role_required(*FRONT_DESK)
def room_board():
    rooms = Room.query.order_by(Room.room_number).all()
    return jsonify(rooms=[r.to_dict() for r in rooms])


@reception_bp.post("/rooms/<int:room_id>/assign-cleaning")
@role_required(*FRONT_DESK)
def assign_cleaning(room_id):
    data = request.get_json(silent=True) or {}
    room = db.get_or_404(Room, room_id)
    room.status = "Cleaning"
    room.assigned_staff = (data.get("assigned_staff") or "").strip() or None
    db.session.commit()
    return jsonify(message="Cleaning assigned", room=room.to_dict())


@reception_bp.get("/housekeepers")
@role_required(*FRONT_DESK)
def housekeepers():
    """Cleaners the desk can hand a room to when flagging it for cleaning."""
    staff = (
        Staff.query.filter_by(role="housekeeping")
        .order_by(Staff.full_name)
        .all()
    )
    return jsonify(
        housekeepers=[{"staff_id": s.staff_id, "full_name": s.full_name} for s in staff]
    )


@reception_bp.get("/bookings")
@role_required(*FRONT_DESK)
def search_bookings():
    """Look up ANY booking by reference or guest name (not just today's).

    Empty query returns the most recent bookings so the desk has a starting list.
    """
    q = (request.args.get("q") or "").strip()
    query = Booking.query.join(Guest)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Booking.reference.ilike(like), Guest.full_name.ilike(like))
        )
    rows = query.order_by(Booking.check_in_date.desc()).limit(50).all()
    out = []
    for b in rows:
        d = b.to_dict()
        d["guest_name"] = b.guest.full_name
        d["guest_email"] = b.guest.email
        d["room_number"] = b.room.room_number
        d["room_type"] = b.room.room_type
        out.append(d)
    return jsonify(bookings=out)


@reception_bp.get("/bookings/<int:booking_id>/invoice")
@role_required(*FRONT_DESK)
def invoice(booking_id):
    """Read-only invoice data for a booking: guest, room, payments, balance.

    The desk renders and prints this in the browser (print -> PDF); nothing is
    stored, so it adds no new dependency or AWS service.
    """
    booking = db.get_or_404(Booking, booking_id)
    paid = sum(float(p.amount) for p in booking.payments)
    total = float(booking.cost_total)
    return jsonify(
        booking=booking.to_dict(),
        guest=booking.guest.to_dict(),
        room=booking.room.to_dict(),
        payments=[p.to_dict() for p in booking.payments],
        amount_paid=round(paid, 2),
        balance_due=round(total - paid, 2),
    )


# --- deletion requests (receptionist raises; a manager must approve) --------
@reception_bp.post("/bookings/<int:booking_id>/deletion-request")
@role_required(*FRONT_DESK)
def request_deletion(booking_id):
    """Ask a manager to delete a booking. Does NOT delete anything itself --
    it records a Pending request that a manager reviews and approves/rejects."""
    data = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if len(reason) < 5:
        return jsonify(error="Please give a reason (at least 5 characters) for the deletion."), 400

    booking = db.get_or_404(Booking, booking_id)

    # One pending request per booking -- don't let the queue fill with duplicates.
    existing = DeletionRequest.query.filter_by(
        booking_id=booking.booking_id, status="Pending"
    ).first()
    if existing:
        return jsonify(error="A deletion request for this booking is already awaiting manager review."), 409

    staff = db.session.get(Staff, session.get("staff_id"))
    req = DeletionRequest(
        booking_id=booking.booking_id,
        booking_reference=booking.reference,
        guest_name=booking.guest.full_name,
        room_number=booking.room.room_number,
        reason=reason,
        requested_by=staff.staff_id if staff else None,
        requested_by_name=staff.full_name if staff else "Unknown",
    )
    db.session.add(req)
    db.session.commit()
    return jsonify(
        message="Deletion request submitted for manager approval",
        deletion_request=req.to_dict(),
    ), 201


@reception_bp.get("/deletion-requests")
@role_required(*FRONT_DESK)
def list_deletion_requests():
    """The desk's view of deletion requests, so a receptionist can see whether
    theirs was approved or rejected. Optional ?status=Pending filter."""
    status = (request.args.get("status") or "").strip()
    query = DeletionRequest.query
    if status:
        query = query.filter_by(status=status)
    rows = query.order_by(DeletionRequest.created_at.desc()).limit(50).all()
    return jsonify(deletion_requests=[r.to_dict() for r in rows])
