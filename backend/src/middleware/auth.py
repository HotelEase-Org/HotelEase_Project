from functools import wraps

from flask import session, jsonify


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("staff_id"):
            return jsonify(error="Authentication required"), 401
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Allow the view only for the given staff roles (also implies login)."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("staff_id"):
                return jsonify(error="Authentication required"), 401
            if session.get("role") not in roles:
                return jsonify(error="Forbidden: insufficient role"), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator
