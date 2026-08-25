from datetime import datetime, timezone

from ..extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class DeletionRequest(db.Model):
    """A receptionist's request to delete a booking, pending manager review.

    Separation of duties: a receptionist can only *request* a deletion; the
    booking is not removed until a manager approves it. The record is also the
    audit trail -- it keeps a snapshot of the booking (reference, guest, room)
    and who requested/reviewed it, so the history survives even after the
    booking row itself is deleted on approval.
    """

    __tablename__ = "deletion_requests"

    request_id = db.Column(db.Integer, primary_key=True)

    # Nullable FK: points at the live booking while Pending, and is cleared to
    # NULL the moment the booking is deleted on approval (the snapshot fields
    # below preserve the details for the audit trail).
    booking_id = db.Column(
        db.Integer, db.ForeignKey("bookings.booking_id"), nullable=True
    )

    # Snapshot of the booking at request time, so the record still reads
    # sensibly after the booking is gone.
    booking_reference = db.Column(db.String(12), nullable=False)
    guest_name = db.Column(db.String(120), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)

    reason = db.Column(db.Text, nullable=False)
    # Pending / Approved / Rejected
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)

    # Who asked and who decided. Nullable FKs plus a name snapshot, because a
    # staff account can be deleted later and we still want the audit trail.
    requested_by = db.Column(
        db.Integer, db.ForeignKey("staff.staff_id"), nullable=True
    )
    requested_by_name = db.Column(db.String(120), nullable=False)
    reviewed_by = db.Column(
        db.Integer, db.ForeignKey("staff.staff_id"), nullable=True
    )
    reviewed_by_name = db.Column(db.String(120), nullable=True)
    review_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "booking_id": self.booking_id,
            "booking_reference": self.booking_reference,
            "guest_name": self.guest_name,
            "room_number": self.room_number,
            "reason": self.reason,
            "status": self.status,
            "requested_by_name": self.requested_by_name,
            "reviewed_by_name": self.reviewed_by_name,
            "review_note": self.review_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }
