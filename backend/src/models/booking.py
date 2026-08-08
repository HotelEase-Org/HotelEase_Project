from ..extensions import db


class Booking(db.Model):
    __tablename__ = "bookings"

    booking_id = db.Column(db.Integer, primary_key=True)
    # Human-friendly, non-sequential code a guest uses to look up their booking.
    reference = db.Column(db.String(12), unique=True, nullable=False, index=True)
    guest_id = db.Column(db.Integer, db.ForeignKey("guests.guest_id"), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.room_id"), nullable=False)
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)
    booking_status = db.Column(db.String(20), nullable=False, default="Pending")
    payment_status = db.Column(db.String(20), nullable=False, default="Unpaid")
    cost_total = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    guest = db.relationship("Guest", back_populates="bookings")
    room = db.relationship("Room", back_populates="bookings")
    payments = db.relationship(
        "Payment", back_populates="booking", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "booking_id": self.booking_id,
            "reference": self.reference,
            "guest_id": self.guest_id,
            "room_id": self.room_id,
            "check_in_date": self.check_in_date.isoformat(),
            "check_out_date": self.check_out_date.isoformat(),
            "booking_status": self.booking_status,
            "payment_status": self.payment_status,
            "cost_total": float(self.cost_total),
        }
