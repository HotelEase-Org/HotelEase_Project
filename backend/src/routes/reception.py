from datetime import date, datetime, timezone

from flask import Blueprint, request, jsonify

from ..extensions import db
from ..models import Booking, Room, Payment
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

    booking = db.get_or_404(Booking, booking_id)
    payment = Payment(
        booking_id=booking.booking_id,
        amount=amount,
        payment_method=method,
        payment_date=datetime.now(timezone.utc),
    )
    db.session.add(payment)

    # Mark paid once total payments cover the booking cost.
    paid = sum(float(p.amount) for p in booking.payments) + float(amount)
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
