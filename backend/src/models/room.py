from ..extensions import db


class Room(db.Model):
    __tablename__ = "rooms"

    room_id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False)
    room_type = db.Column(db.String(40), nullable=False)
    rate_per_night = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Available")
    assigned_staff = db.Column(db.String(120))
    last_cleaned = db.Column(db.DateTime)

    bookings = db.relationship("Booking", back_populates="room")

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "room_number": self.room_number,
            "room_type": self.room_type,
            "rate_per_night": float(self.rate_per_night),
            "status": self.status,
            "assigned_staff": self.assigned_staff,
            "last_cleaned": self.last_cleaned.isoformat() if self.last_cleaned else None,
        }
