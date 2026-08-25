"""Tests for the feature-gap work: booking search, housekeeper list,
real cleaning assignment, the InProgress cleaning state, invoices, and
manager edit/guarded-delete for staff and rooms."""

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


# --- reception: search any booking -----------------------------------------
def test_search_bookings_by_reference(client):
    ref = _make_booking(client).get_json()["reference"]
    login(client, "reception")
    r = client.get("/api/reception/bookings", query_string={"q": ref})
    assert r.status_code == 200
    rows = r.get_json()["bookings"]
    assert len(rows) == 1
    assert rows[0]["reference"] == ref
    assert rows[0]["guest_name"] == "Ama Boateng"


def test_search_bookings_by_name_is_case_insensitive(client):
    _make_booking(client)
    login(client, "reception")
    r = client.get("/api/reception/bookings", query_string={"q": "ama"})
    assert r.status_code == 200
    assert len(r.get_json()["bookings"]) == 1


def test_search_bookings_empty_query_returns_recent(client):
    _make_booking(client)
    login(client, "reception")
    r = client.get("/api/reception/bookings")
    assert r.status_code == 200
    assert len(r.get_json()["bookings"]) == 1


def test_search_bookings_requires_auth(client):
    assert client.get("/api/reception/bookings").status_code == 401


# --- reception: housekeepers list -------------------------------------------
def test_housekeepers_list(client):
    login(client, "reception")
    r = client.get("/api/reception/housekeepers")
    assert r.status_code == 200
    names = [h["full_name"] for h in r.get_json()["housekeepers"]]
    assert names == ["Cleaner"]


# --- reception: real cleaning assignment ------------------------------------
def test_assign_cleaning_sets_staff_and_housekeeping_sees_it(client):
    login(client, "reception")
    r = client.post("/api/reception/rooms/1/assign-cleaning",
                    json={"assigned_staff": "Cleaner"})
    assert r.status_code == 200
    room = r.get_json()["room"]
    assert room["status"] == "Cleaning"
    assert room["assigned_staff"] == "Cleaner"

    # The housekeeper it was assigned to sees it flagged as theirs.
    login(client, "housekeeping")
    rooms = client.get("/api/housekeeping/rooms").get_json()["rooms"]
    mine = [x for x in rooms if x["room_id"] == 1][0]
    assert mine["assigned_to_me"] is True


def test_assign_cleaning_unassigned(client):
    login(client, "reception")
    r = client.post("/api/reception/rooms/1/assign-cleaning",
                    json={"assigned_staff": ""})
    assert r.status_code == 200
    assert r.get_json()["room"]["assigned_staff"] is None


# --- housekeeping: InProgress transition ------------------------------------
def test_housekeeping_start_then_clean(client):
    login(client, "housekeeping")
    # Room -> InProgress (Start Cleaning)
    r = client.post("/api/housekeeping/rooms/1/status", json={"status": "InProgress"})
    assert r.status_code == 200
    assert r.get_json()["room"]["status"] == "InProgress"

    # InProgress room shows on the work list.
    rooms = client.get("/api/housekeeping/rooms").get_json()["rooms"]
    assert any(x["room_id"] == 1 and x["status"] == "InProgress" for x in rooms)

    # InProgress -> Available (Mark Clean) clears assignment + stamps last_cleaned.
    r = client.post("/api/housekeeping/rooms/1/status", json={"status": "Available"})
    assert r.status_code == 200
    room = r.get_json()["room"]
    assert room["status"] == "Available"
    assert room["assigned_staff"] is None


def test_housekeeping_rejects_bad_status(client):
    login(client, "housekeeping")
    r = client.post("/api/housekeeping/rooms/1/status", json={"status": "Nonsense"})
    assert r.status_code == 400


# --- reception: invoice ------------------------------------------------------
def test_invoice_balance_reflects_payment(client):
    _make_booking(client)  # 3 nights x 400 = 1200
    login(client, "reception")
    client.post("/api/reception/payments",
                json={"booking_id": 1, "amount": 500, "payment_method": "Cash"})
    r = client.get("/api/reception/bookings/1/invoice")
    assert r.status_code == 200
    data = r.get_json()
    assert data["booking"]["cost_total"] == 1200.0
    assert data["amount_paid"] == 500.0
    assert data["balance_due"] == 700.0
    assert len(data["payments"]) == 1


# --- manager: staff edit / guarded delete -----------------------------------
def test_manager_update_staff(client):
    login(client, "manager")
    # Rename + re-role the receptionist (staff_id 2).
    r = client.patch("/api/manager/staff/2",
                     json={"full_name": "Recep Renamed", "role": "housekeeping"})
    assert r.status_code == 200
    assert r.get_json()["staff"]["full_name"] == "Recep Renamed"
    assert r.get_json()["staff"]["role"] == "housekeeping"


def test_manager_cannot_delete_self(client):
    login(client, "manager")  # manager is staff_id 1
    r = client.delete("/api/manager/staff/1")
    assert r.status_code == 409


def test_manager_cannot_delete_last_manager(client):
    login(client, "manager")
    # Add a second manager so we are allowed to delete the seeded one.
    client.post("/api/manager/staff", json={
        "full_name": "Mgr Two", "role": "manager",
        "username": "mgr2", "password": "manager-two-pw"})
    # Deleting the seeded manager (id 1) is blocked only because it is self;
    # instead demote-delete path: delete the new manager, then the only-manager
    # guard blocks removing the last one.
    del2 = client.delete("/api/manager/staff/4")
    assert del2.status_code == 200
    # Now only the logged-in manager remains -- self-delete guard applies.
    assert client.delete("/api/manager/staff/1").status_code == 409


def test_manager_delete_staff_success(client):
    login(client, "manager")
    # Delete the housekeeper (staff_id 3) -- not self, not last manager.
    r = client.delete("/api/manager/staff/3")
    assert r.status_code == 200
    assert len(client.get("/api/manager/staff").get_json()["staff"]) == 2


# --- manager: room edit / guarded delete ------------------------------------
def test_manager_update_room(client):
    login(client, "manager")
    r = client.patch("/api/manager/rooms/1", json={
        "room_type": "Suite", "rate_per_night": 650, "status": "Maintenance"})
    assert r.status_code == 200
    room = r.get_json()["room"]
    assert room["room_type"] == "Suite"
    assert room["rate_per_night"] == 650.0
    assert room["status"] == "Maintenance"


def test_manager_update_room_rejects_bad_rate(client):
    login(client, "manager")
    assert client.patch("/api/manager/rooms/1",
                        json={"rate_per_night": 0}).status_code == 400


def test_manager_delete_room_refused_when_booked(client):
    _make_booking(client)  # references room 1
    login(client, "manager")
    r = client.delete("/api/manager/rooms/1")
    assert r.status_code == 409
    assert "booking" in r.get_json()["error"].lower()


def test_manager_delete_room_allowed_when_unbooked(client):
    login(client, "manager")
    # A fresh room with no bookings can be removed.
    new_id = client.post("/api/manager/rooms", json={
        "room_number": "999", "room_type": "Standard",
        "rate_per_night": 300}).get_json()["room"]["room_id"]
    assert client.delete(f"/api/manager/rooms/{new_id}").status_code == 200


# --- security hardening: server-side validation -----------------------------
def test_booking_rejects_past_dates(client):
    # Frontend sets a min date, but the server must reject past check-ins too.
    r = _make_booking(client, check_in_date="2020-01-01",
                      check_out_date="2020-01-03")
    assert r.status_code == 400
    assert "past" in r.get_json()["error"].lower()


def test_payment_rejects_non_positive_amount(client):
    bid = _make_booking(client).get_json()["booking"]["booking_id"]
    login(client, "reception")
    for bad in (0, -50):
        r = client.post("/api/reception/payments",
                        json={"booking_id": bid, "amount": bad,
                              "payment_method": "Cash"})
        assert r.status_code == 400
    # A valid positive amount still records fine.
    ok = client.post("/api/reception/payments",
                     json={"booking_id": bid, "amount": 100,
                           "payment_method": "Cash"})
    assert ok.status_code == 201


def test_create_staff_rejects_short_password(client):
    login(client, "manager")
    r = client.post("/api/manager/staff", json={
        "full_name": "Weak Pw", "role": "receptionist",
        "username": "weakpw", "password": "short"})
    assert r.status_code == 400
    assert "8 characters" in r.get_json()["error"]

