"""S3 storage service -- streams guest ID documents to a private S3 bucket.

Design notes:
  - The file is streamed straight to S3 and is NEVER written to local disk
    (no .save()), which is the course requirement for user-uploaded assets.
  - Credentials come from the EC2 instance role (hotelease-ec2-role), so no
    access keys are stored in code or config. boto3 finds them automatically.
  - The bucket is private with all public access blocked. Only the object key
    is kept in the database; the object itself is never publicly reachable.
"""
import uuid

import boto3
from flask import current_app

# Accepted MIME types mapped to the extension we assign. We assign the
# extension ourselves and never trust the client-supplied filename.
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}

MAX_BYTES = 5 * 1024 * 1024  # 5 MB


# Magic-byte signatures, so we validate the real file content instead of
# trusting the client-supplied MIME type. Each allowed type must start with
# one of these byte prefixes.
MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "application/pdf": (b"%PDF-",),
}


class UploadError(ValueError):
    """Raised when an uploaded file is missing or fails validation."""


def _client():
    # Region from config; credentials resolved from the instance role at runtime.
    region = current_app.config.get("AWS_REGION", "eu-west-1")
    return boto3.client("s3", region_name=region)


def upload_id_document(file_storage):
    """Validate a Werkzeug FileStorage and stream it to S3.

    Returns the S3 object key (e.g. "guest-ids/<uuid>.jpg").
    Raises UploadError (a ValueError subclass) if the file is missing or invalid.
    """
    if file_storage is None or not file_storage.filename:
        raise UploadError("An ID document file is required.")

    content_type = (file_storage.mimetype or "").lower()
    ext = ALLOWED_TYPES.get(content_type)
    if ext is None:
        raise UploadError("ID document must be a JPG, PNG, or PDF file.")

    # Measure the real stream size instead of trusting any client header.
    stream = file_storage.stream
    stream.seek(0, 2)          # seek to end
    size = stream.tell()
    stream.seek(0)             # rewind so the whole file uploads
    if size == 0:
        raise UploadError("The uploaded file is empty.")
    if size > MAX_BYTES:
        raise UploadError("ID document must be 5 MB or smaller.")

    # Sniff the leading bytes and confirm they match the declared type, so a
    # renamed executable or spoofed Content-Type can't slip through.
    header = stream.read(8)
    stream.seek(0)
    if not any(header.startswith(sig) for sig in MAGIC[content_type]):
        raise UploadError("The file content does not match a JPG, PNG, or PDF.")

    bucket = current_app.config.get("S3_BUCKET", "hotelease-uploads")
    key = f"guest-ids/{uuid.uuid4().hex}{ext}"
    _client().upload_fileobj(
        stream,
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},  # no ACL -> object stays private
    )
    return key
