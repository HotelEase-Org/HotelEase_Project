# HotelEase -- Backend (Python / Flask)

REST API for HotelEase, the hotel management system. Built with Flask +
Flask-SQLAlchemy following a simple MVC layout. Runs on SQLite locally with zero
setup, and switches to PostgreSQL (Amazon RDS) in production by setting one
environment variable.

## 1. Requirements

- Python 3.10+
- pip / venv

## 2. Setup and run (local)

From inside the `backend/` folder:

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python seed.py                    # creates instance/hotelease.db with demo data
python run.py                     # serves on http://localhost:5000
```

Health check: open <http://localhost:5000/api/health> -- you should see
`{"status": "ok", "service": "hotelease-api"}`.

Run the tests:

```bash
python -m pytest -q               # 9 tests, all should pass
```

## 3. Demo accounts (created by seed.py)

`seed.py` creates one account per role. It prints each account's password once
when you run it -- set `SEED_MANAGER_PASSWORD`, `SEED_RECEPTION_PASSWORD`, and
`SEED_HOUSEKEEPING_PASSWORD` to choose your own, otherwise a random password is
generated. Passwords are deliberately not committed to the repo.

| Role         | Username       |
|--------------|----------------|
| Manager      | `manager`      |
| Receptionist | `reception`    |
| Housekeeping | `housekeeping` |

`seed.py` also prints a demo booking reference (for testing the guest lookup).

## 4. Project layout

```
backend/
  run.py                 Dev entry point (python run.py)
  seed.py                Reset + populate the database with demo data
  requirements.txt       Python dependencies
  .env.example           Copy to .env and fill in for real deployments
  src/
    __init__.py          App factory: CORS, blueprints, db, /api/health
    config.py            SQLite locally / PostgreSQL via DATABASE_URL
    extensions.py        Shared SQLAlchemy instance (db)
    models/              Guest, Room, Booking, Payment, Staff (matches the ERD)
    middleware/auth.py   login_required + role_required decorators
    controllers/         availability.py: double-booking check, reference codes
    routes/              auth, guest (public), reception, housekeeping, manager
  tests/                 pytest suite (test client, in-memory DB)
```

## 5. Configuration

Copy `.env.example` to `.env` and adjust. `.env` is gitignored -- never commit
real secrets.

| Variable       | Purpose                                                        |
|----------------|----------------------------------------------------------------|
| `SECRET_KEY`   | Flask session signing key. Use a long random string.           |
| `DATABASE_URL` | Empty = local SQLite. Set to the RDS PostgreSQL URL in prod.   |
| `CORS_ORIGINS` | Allowed frontend origins. `*` for local dev only.              |

Production (RDS) example:

```
DATABASE_URL=postgresql://USER:PASSWORD@YOUR-RDS-ENDPOINT:5432/hotelease
```

## 6. API endpoints

Auth uses a signed session cookie. Staff routes are role-gated; guest routes are
public (no login).

### Public (guest)
| Method | Path                     | Purpose                                   |
|--------|--------------------------|-------------------------------------------|
| GET    | `/api/health`            | Service health check                      |
| GET    | `/api/rooms/available`   | Rooms free for `?check_in=&check_out=`    |
| POST   | `/api/bookings`          | Submit a booking, returns a reference ID  |
| GET    | `/api/bookings/lookup`   | Status by `?reference=&email=`            |

### Auth
| Method | Path               | Purpose                          |
|--------|--------------------|----------------------------------|
| POST   | `/api/auth/login`  | Log in (username + password)     |
| POST   | `/api/auth/logout` | Log out                          |
| GET    | `/api/auth/me`     | Current session / logged-in user |

### Receptionist (role: receptionist, manager)
| Method | Path                                             | Purpose                 |
|--------|--------------------------------------------------|-------------------------|
| GET    | `/api/reception/dashboard`                       | Front-desk KPIs         |
| GET    | `/api/reception/arrivals`                        | Today's arrivals/depart |
| POST   | `/api/reception/bookings/<id>/check-in`          | Check a guest in        |
| POST   | `/api/reception/bookings/<id>/check-out`         | Check a guest out       |
| POST   | `/api/reception/payments`                        | Record a payment        |
| GET    | `/api/reception/rooms`                           | Room status board       |
| POST   | `/api/reception/rooms/<id>/assign-cleaning`      | Assign a cleaning job   |

### Housekeeping (role: housekeeping, manager)
| Method | Path                                              | Purpose               |
|--------|---------------------------------------------------|-----------------------|
| GET    | `/api/housekeeping/rooms`                          | Rooms needing work    |
| POST   | `/api/housekeeping/rooms/<id>/status`             | Update room status    |
| POST   | `/api/housekeeping/rooms/<id>/flag-maintenance`   | Flag for maintenance  |

### Manager (role: manager)
| Method | Path                     | Purpose                              |
|--------|--------------------------|--------------------------------------|
| GET    | `/api/manager/analytics` | Revenue trend, occupancy, bookings   |
| GET    | `/api/manager/staff`     | List staff accounts                  |
| POST   | `/api/manager/staff`     | Create a staff account               |
| GET    | `/api/manager/rooms`     | Room inventory                       |
| POST   | `/api/manager/rooms`     | Add a room                           |

## 7. Key design decisions

- **Double-booking prevention** lives in `controllers/availability.py`. A room is
  unavailable when an existing active booking overlaps the requested dates
  (`existing.check_in < new.check_out AND existing.check_out > new.check_in`).
- **Booking references** are short, non-sequential codes (`HE-XXXXXX`) so guests
  can look up a reservation without an account, using reference + email.
- **Roles** are enforced by the `role_required(...)` decorator in
  `middleware/auth.py`; the manager role is allowed on front-desk and
  housekeeping routes as a supervisor.
- **SQLite now, PostgreSQL later**: the same code runs on RDS by setting
  `DATABASE_URL`. No code changes needed for deployment.

## 8. Notes

- `venv/`, `instance/` (the local database), `__pycache__/`, and `.env` are
  gitignored -- do not commit them.
- The database schema is created automatically on first run
  (`db.create_all()` in the app factory), and `seed.py` resets it with demo data.
