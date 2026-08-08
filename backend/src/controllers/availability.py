import secrets
import string

from ..models import Booking

# Statuses that still hold a room (block overlapping bookings).
ACTIVE_STATUSES = ("Pending", "Confirmed", "CheckedIn")


def is_room_available(room_id, check_in, check_out, exclude_booking_id=None):
    """Return True if the room has no overlapping active booking.

    Overlap rule: an existing booking conflicts when
        existing.check_in < new.check_out AND existing.check_out > new.check_in
    """
    q = Booking.query.filter(
        Booking.room_id == room_id,
        Booking.booking_status.in_(ACTIVE_STATUSES),
        Booking.check_in_date < check_out,
        Booking.check_out_date > check_in,
    )
    if exclude_booking_id is not None:
        q = q.filter(Booking.booking_id != exclude_booking_id)
    return q.first() is None


def generate_reference():
    """Short, non-sequential booking reference, e.g. HE-7QK2P9."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        ref = "HE-" + "".join(secrets.choice(alphabet) for _ in range(6))
        if Booking.query.filter_by(reference=ref).first() is None:
            return ref


def nights_between(check_in, check_out):
    return (check_out - check_in).days
