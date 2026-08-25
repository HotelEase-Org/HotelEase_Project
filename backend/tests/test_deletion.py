"""Tests for the manager-approved booking-deletion workflow.

A receptionist can only *request* a deletion (with a reason); the booking is
removed only after a manager approves. Rejected requests leave the booking
intact. A reviewer cannot decide on a request they raised themselves.
"""

from tests.conftest import login


def _make_booking(client, **overrides):
    data = {
        "full_name": "Ama Boateng",
        "email": "ama@example.com",
        "phone_number": "0201112222",
        "room_id": 1,
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-04",
    }
    data.update(overrides)
    return client.post("/api/bookings", json=data)


def _booking_id(client, **overrides):
    return _make_booking(client, **overrides).get_json()["booking"]["booking_id"]


def _request_deletion(client, booking_id, reason="Guest cancelled by phone"):
    return client.post(
        f"/api/reception/bookings/{booking_id}/deletion-request",
        json={"reason": reason},
    )


# --- raising a request ------------------------------------------------------
def test_request_deletion_creates_pending_and_keeps_booking(client):
    bid = _booking_id(client)
    login(client, "reception")
    r = _request_deletion(client, bid)
    assert r.status_code == 201
    assert r.get_json()["deletion_request"]["status"] == "Pending"
    # The booking is untouched until a manager approves.
    assert client.get(f"/api/reception/bookings/{bid}/invoice").status_code == 200


def test_request_deletion_requires_reason(client):
    bid = _booking_id(client)
    login(client, "reception")
    assert _request_deletion(client, bid, reason="no").status_code == 400


def test_request_deletion_rejects_duplicate_pending(client):
    bid = _booking_id(client)
    login(client, "reception")
    assert _request_deletion(client, bid).status_code == 201
    assert _request_deletion(client, bid).status_code == 409


def test_request_deletion_requires_auth(client):
    bid = _booking_id(client)
    assert _request_deletion(client, bid).status_code == 401


def test_housekeeping_cannot_request_deletion(client):
    bid = _booking_id(client)
    login(client, "housekeeping")
    assert _request_deletion(client, bid).status_code == 403


# --- manager review ---------------------------------------------------------
def test_manager_lists_pending_requests(client):
    bid = _booking_id(client)
    login(client, "reception")
    _request_deletion(client, bid)
    login(client, "manager")
    rows = client.get("/api/manager/deletion-requests").get_json()["deletion_requests"]
    assert len(rows) == 1
    assert rows[0]["status"] == "Pending"
    assert rows[0]["requested_by_name"] == "Recep"


def test_manager_approve_deletes_booking(client):
    bid = _booking_id(client)
    login(client, "reception")
    # A payment on the booking must cascade away cleanly on delete.
    client.post("/api/reception/payments",
                json={"booking_id": bid, "amount": 100, "payment_method": "Cash"})
    req_id = _request_deletion(client, bid).get_json()["deletion_request"]["request_id"]

    login(client, "manager")
    r = client.post(f"/api/manager/deletion-requests/{req_id}/approve",
                    json={"note": "Confirmed with guest"})
    assert r.status_code == 200
    dr = r.get_json()["deletion_request"]
    assert dr["status"] == "Approved"
    assert dr["reviewed_by_name"] == "Manager"
    # Snapshot survives even though the booking row is gone.
    assert dr["booking_reference"].startswith("HE-")
    assert dr["booking_id"] is None
    # Booking is actually deleted.
    assert client.get(f"/api/reception/bookings/{bid}/invoice").status_code == 404


def test_manager_reject_keeps_booking(client):
    bid = _booking_id(client)
    login(client, "reception")
    req_id = _request_deletion(client, bid).get_json()["deletion_request"]["request_id"]

    login(client, "manager")
    r = client.post(f"/api/manager/deletion-requests/{req_id}/reject",
                    json={"note": "Not enough justification"})
    assert r.status_code == 200
    assert r.get_json()["deletion_request"]["status"] == "Rejected"
    # Booking stays put.
    assert client.get(f"/api/reception/bookings/{bid}/invoice").status_code == 200


def test_receptionist_cannot_approve(client):
    bid = _booking_id(client)
    login(client, "reception")
    req_id = _request_deletion(client, bid).get_json()["deletion_request"]["request_id"]
    # Still logged in as reception -- approval is manager-only.
    assert client.post(f"/api/manager/deletion-requests/{req_id}/approve").status_code == 403


def test_cannot_decide_twice(client):
    bid = _booking_id(client)
    login(client, "reception")
    req_id = _request_deletion(client, bid).get_json()["deletion_request"]["request_id"]
    login(client, "manager")
    assert client.post(f"/api/manager/deletion-requests/{req_id}/reject").status_code == 200
    # Second decision on the same request is a conflict.
    assert client.post(f"/api/manager/deletion-requests/{req_id}/approve").status_code == 409


def test_manager_cannot_review_own_request(client):
    bid = _booking_id(client)
    # A manager can use the front desk, so a manager can raise a request...
    login(client, "manager")
    req_id = _request_deletion(client, bid).get_json()["deletion_request"]["request_id"]
    # ...but cannot approve their own (separation of duties).
    assert client.post(f"/api/manager/deletion-requests/{req_id}/approve").status_code == 403
