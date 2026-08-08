from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db


class Staff(db.Model):
    __tablename__ = "staff"

    staff_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    # role: receptionist / housekeeping / manager
    role = db.Column(db.String(20), nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "staff_id": self.staff_id,
            "full_name": self.full_name,
            "role": self.role,
            "username": self.username,
        }
