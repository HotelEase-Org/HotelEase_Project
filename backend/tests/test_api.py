from tests.conftest import login


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def _booking_payload(**overrides):
    data = {
        "full_name": "Yaw Test",
        "email": "yaw@example.com",
        "phone_number": "0201112222",
        "room_id": 1,
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-04",
    }
    data.update(overrides)
    return data


def test_create_booking_returns_reference(client):
    r = client.post("/api/bookings", json=_booking_payload())
    assert r.status_code == 201
    body = r.get_json()
    assert body["reference"].startswith("HE-")
    # 3 nights x 400 = 1200
    assert body["booking"]["cost_total"] == 1200.0


def test_double_booking_is_rejected(client):
    assert client.post("/api/bookings", json=_booking_payload()).status_code == 201
    # Overlapping dates on the same room must be refused.
    clash = client.post("/api/bookings", json=_booking_payload(
        email="other@example.com", check_in_date="2026-09-02",
        check_out_date="2026-09-05"))
    assert clash.status_code == 409


def test_non_overlapping_booking_is_allowed(client):
    assert client.post("/api/bookings", json=_booking_payload()).status_code == 201
    later = client.post("/api/bookings", json=_booking_payload(
        email="later@example.com", check_in_date="2026-09-04",
        check_out_date="2026-09-06"))
    assert later.status_code == 201


def test_lookup_requires_matching_email(client):
    ref = client.post("/api/bookings", json=_booking_payload()).get_json()["reference"]
    ok = client.get(f"/api/bookings/lookup?reference={ref}&email=yaw@example.com")
    assert ok.status_code == 200
    wrong = client.get(f"/api/bookings/lookup?reference={ref}&email=nope@example.com")
    assert wrong.status_code == 404


def test_manager_route_requires_auth(client):
    assert client.get("/api/manager/analytics").status_code == 401


def test_manager_route_rejects_wrong_role(client):
    login(client, "reception")
    assert client.get("/api/manager/analytics").status_code == 403


def test_manager_route_allows_manager(client):
    login(client, "manager")
    assert client.get("/api/manager/analytics").status_code == 200


def test_reception_dashboard(client):
    login(client, "reception")
    r = client.get("/api/reception/dashboard")
    assert r.status_code == 200
    assert "rooms_occupied" in r.get_json()
