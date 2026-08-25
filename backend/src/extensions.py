from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Single shared SQLAlchemy instance, initialised in the app factory.
db = SQLAlchemy()

# Rate limiter, keyed by client IP. No global default limit -- we opt specific
# sensitive endpoints (e.g. login) in with @limiter.limit(...). Storage is
# in-memory, which is fine for a single-instance deployment; note that with
# multiple Gunicorn workers each worker keeps its own counter, so the effective
# limit is per-worker. A shared store (Redis) would be needed for exactness.
limiter = Limiter(key_func=get_remote_address, default_limits=[])

