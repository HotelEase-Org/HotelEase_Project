# HotelEase -- Frontend

The browser UI for HotelEase. Plain HTML, CSS and vanilla JavaScript (no build
step, no framework) that talks to the Flask API in `../backend` over `fetch`.

Kept deliberately simple so it can be hosted as static files (Amazon S3 static
website, or served by the Flask app itself) on the AWS Free Tier.

## Layout

```
frontend/
  index.html            redirect -> pages/index.html
  css/
    styles.css          design system (layout, top bar, sidebar shell)
    components.css       cards, tables, badges, buttons, forms, charts
    app.css              runtime bits: alerts, toasts, modal, spinner
  js/
    api.js              API_BASE + fetch wrapper + Auth + requireRole() guard
    ui.js               formatting (money/date), status->badge, alerts, modal
    booking.js          guest page logic
    login.js            staff sign in
    reception.js        front desk dashboard
    housekeeping.js     cleaning work list
    manager.js          analytics, staff, room inventory
  pages/
    index.html          Guest: book a room + check my booking (public)
    login.html          Staff login
    reception.html      Receptionist / Manager
    housekeeping.html   Housekeeping / Manager
    manager.html        Manager only
```

## Running it locally

You need the **backend running first** (see `../backend/README.md`):

```bash
cd ../backend
source venv/bin/activate
python seed.py      # first time only -- creates demo data
python run.py       # serves the API on http://localhost:5000
```

Then serve these static files from a second terminal. Any static server works;
Python's built-in one is easiest:

```bash
cd frontend
python -m http.server 8080
```

Open **http://localhost:8080/** in your browser.

> **Why a separate server (not just double-clicking the HTML)?**
> Opening a file with `file://` blocks `fetch` and cookies. Serving over
> `http://localhost` makes the session login work.

### Demo accounts

| Role         | Username       | Password       |
|--------------|----------------|----------------|
| Manager      | `manager`      | `manager123`   |
| Receptionist | `reception`    | `reception123` |
| Housekeeping | `housekeeping` | `cleaning123`  |

## How it connects to the API

`js/api.js` has a single setting at the top:

```js
const API_BASE = "http://localhost:5000";
```

- **Local dev:** leave it as is (frontend on `:8080`, API on `:5000`).
- **Flask serves these files (same origin):** set `API_BASE = ""`.
- **Production (separate hosts):** set it to your EC2 API URL, e.g.
  `"https://api.hotelease.example.com"`.

Every request is sent with `credentials: "include"` so the Flask session cookie
rides along, and each staff page calls `requireRole([...])` on load -- if you're
not signed in (or have the wrong role) it redirects to the login page.

### CORS / cookies notes

- Local dev works with the backend's default `CORS_ORIGINS`, because Flask-CORS
  echoes the request origin when credentials are enabled. The cross-port cookie
  (`:8080` -> `:5000`) is sent because the browser treats them as the same site.
- **Deploying the frontend on a different domain than the API** (e.g. S3 for the
  site, EC2 for the API) is cross-site. For the session cookie to be sent there,
  the backend must set the cookie with `SameSite=None; Secure` and both sides
  must be served over HTTPS, and `CORS_ORIGINS` must list the site's exact origin.
  The simplest alternative is to let Flask serve this `frontend/` folder so the
  API and UI share one origin -- then no cross-site cookie config is needed.

## What each page does

- **Guest (`index.html`)** -- pick dates, see live availability (double-booking is
  prevented server-side), submit a booking and get a reference; look up an
  existing booking by reference + email.
- **Login** -- signs in, then redirects to the dashboard for your role.
- **Reception** -- KPIs, today's arrivals/departures with check-in / check-out,
  record a payment, a live room status board, and flag a room for cleaning.
- **Housekeeping** -- rooms needing attention; mark a room clean (back to
  Available) or flag it for maintenance.
- **Manager** -- revenue and occupancy KPIs, a revenue trend bar chart and a
  bookings-by-room-type donut, plus staff accounts and room inventory with
  "Add" dialogs.
