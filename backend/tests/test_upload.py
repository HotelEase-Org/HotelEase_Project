"""Endpoint tests for the guest ID-document upload (Kenneth's part).

These exercise POST /api/bookings with multipart/form-data. The real S3 client
is replaced with a stub, so the tests validate our own code (type/size checks,
route wiring, the has_id_document flag) without ever touching AWS. No AWS
credentials are needed to run them.
"""
import io

import pytest


class _FakeS3:
    """Stands in for a boto3 S3 client so tests never hit the network."""

    def __init__(self):
        self.uploads = []

    def upload_fileobj(self, stream, bucket, key, ExtraArgs=None):
        # Record the call and return -- no real upload happens.
        self.uploads.append((bucket, key, ExtraArgs))


@pytest.fixture
def fake_s3(monkeypatch):
    """Swap the storage module's S3 client factory for a no-op stub.

    upload_id_document() still runs its real validation (mimetype + size); only
    the actual put to S3 is faked, so a valid file is 'uploaded' to the stub.
    """
    fake = _FakeS3()
    monkeypatch.setattr("src.services.storage._client", lambda: fake)
    return fake


def _fields(**overrides):
    # room_id is a string here because form fields are always strings.
    data = {
        "full_name": "Yaw Test",
        "email": "yaw@example.com",
        "phone_number": "0201112222",
        "room_id": "1",
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-04",
    }
    data.update(overrides)
    return data


# A tiny stand-in for an image/PDF body -- content is never inspected, only the
# declared MIME type and the byte length matter to the validator.
SMALL_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 256


def test_multipart_upload_stores_key(client, fake_s3):
    data = _fields()
    data["id_document"] = (io.BytesIO(SMALL_BYTES), "id.jpg", "image/jpeg")
    r = client.post("/api/bookings", data=data, content_type="multipart/form-data")

    assert r.status_code == 201
    body = r.get_json()
    assert body["booking"]["has_id_document"] is True
    # The file was streamed to S3 (our stub) under a guest-ids/ key.
    assert len(fake_s3.uploads) == 1
    _bucket, key, _extra = fake_s3.uploads[0]
    assert key.startswith("guest-ids/")
    assert key.endswith(".jpg")


def test_pdf_upload_is_accepted(client, fake_s3):
    data = _fields(email="pdf@example.com")
    data["id_document"] = (io.BytesIO(b"%PDF-1.4 fake"), "id.pdf", "application/pdf")
    r = client.post("/api/bookings", data=data, content_type="multipart/form-data")

    assert r.status_code == 201
    assert r.get_json()["booking"]["has_id_document"] is True
    assert fake_s3.uploads[0][1].endswith(".pdf")


def test_wrong_file_type_is_rejected(client, fake_s3):
    data = _fields(email="wrong@example.com")
    data["id_document"] = (io.BytesIO(b"just some text"), "notes.txt", "text/plain")
    r = client.post("/api/bookings", data=data, content_type="multipart/form-data")

    assert r.status_code == 400
    assert "JPG" in r.get_json()["error"]
    assert fake_s3.uploads == []  # nothing streamed when the type is rejected


def test_oversize_file_is_rejected(client, fake_s3):
    big = io.BytesIO(b"0" * (5 * 1024 * 1024 + 1))  # 1 byte over 5 MB
    data = _fields(email="big@example.com")
    data["id_document"] = (big, "big.png", "image/png")
    r = client.post("/api/bookings", data=data, content_type="multipart/form-data")

    assert r.status_code == 400
    assert "5 MB" in r.get_json()["error"]
    assert fake_s3.uploads == []


def test_empty_file_is_rejected(client, fake_s3):
    data = _fields(email="empty@example.com")
    data["id_document"] = (io.BytesIO(b""), "empty.jpg", "image/jpeg")
    r = client.post("/api/bookings", data=data, content_type="multipart/form-data")

    assert r.status_code == 400
    assert fake_s3.uploads == []


def test_multipart_without_file_still_books(client, fake_s3):
    # The upload is enforced in the browser (the form field is required); the
    # API keeps it optional so older JSON callers stay compatible. A multipart
    # request with no file must still create a booking, with no S3 upload.
    r = client.post("/api/bookings", data=_fields(email="nofile@example.com"),
                    content_type="multipart/form-data")

    assert r.status_code == 201
    assert r.get_json()["booking"]["has_id_document"] is False
    assert fake_s3.uploads == []
