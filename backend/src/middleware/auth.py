from functools import wraps

from flask import session, jsonify

from ..extensions import db
from ..models import Staff


def _current_staff():
    """Resolve the logged-in Staff row from the session cookie.

    The session cookie carries only an id and role, both signed but stale: they
    reflect the account as it was at login. We reload the Staff row on every
    guarded request so that an account which has since been deleted or had its
    role changed is authorised against the live database, not the old claims.
    Returns None when there is no session or the account no longer exists.
    """
    staff_id = session.get("staff_id")
    if not staff_id:
        return None
    return db.session.get(Staff, staff_id)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _current_staff() is None:
            session.clear()
            return jsonify(error="Authentication required"), 401
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Allow the view only for the given staff roles (also implies login)."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            staff = _current_staff()
            if staff is None:
                session.clear()
                return jsonify(error="Authentication required"), 401
            # Authorise against the current database role, not the cookie's.
            if staff.role not in roles:
                return jsonify(error="Forbidden: insufficient role"), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator
