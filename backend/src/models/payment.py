from datetime import datetime, timezone

from ..extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class Payment(db.Model):
    __tablename__ = "payments"

    payment_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(
        db.Integer, db.ForeignKey("bookings.booking_id"), nullable=False
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False, default=_utcnow)

    booking = db.relationship("Booking", back_populates="payments")

    def to_dict(self):
        return {
            "payment_id": self.payment_id,
            "booking_id": self.booking_id,
            "amount": float(self.amount),
            "payment_method": self.payment_method,
            "payment_date": self.payment_date.isoformat(),
        }
