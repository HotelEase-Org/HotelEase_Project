from flask import Blueprint, request, jsonify, session

from ..extensions import db
from ..models import Staff

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    staff = Staff.query.filter_by(username=username).first()
    if staff is None or not staff.check_password(password):
        return jsonify(error="Invalid username or password"), 401

    session.clear()
    session["staff_id"] = staff.staff_id
    session["role"] = staff.role
    return jsonify(message="Logged in", user=staff.to_dict())


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out")


@auth_bp.get("/me")
def me():
    staff_id = session.get("staff_id")
    if not staff_id:
        return jsonify(authenticated=False), 200
    staff = db.session.get(Staff, staff_id)
    if staff is None:
        session.clear()
        return jsonify(authenticated=False), 200
    return jsonify(authenticated=True, user=staff.to_dict())
