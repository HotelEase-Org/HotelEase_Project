from ..extensions import db


class Guest(db.Model):
    __tablename__ = "guests"

    guest_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    id_number = db.Column(db.String(60))

    bookings = db.relationship(
        "Booking", back_populates="guest", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "guest_id": self.guest_id,
            "full_name": self.full_name,
            "phone_number": self.phone_number,
            "email": self.email,
            "id_number": self.id_number,
        }
