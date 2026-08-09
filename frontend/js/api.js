/* ============================================================
   api.js -- the single place the frontend talks to the Flask API
   ============================================================ */

/*
 * API_BASE points at the Flask backend.
 *
 *  - Local dev:  backend runs on http://localhost:5000, these pages are served
 *                separately (e.g. `python -m http.server 8080` in /frontend).
 *                Leave the default below.
 *  - Same origin: if Flask itself serves these files, set API_BASE = "".
 *  - Production:  set API_BASE to your EC2 API URL, e.g.
 *                 "https://api.hotelease.example.com"
 *
 * Every request sends credentials so the Flask session cookie rides along.
 */
const API_BASE = "http://localhost:5000";

/**
 * Core request helper. Returns parsed JSON on success.
 * Throws an Error (with .status and .data) on any non-2xx response so callers
 * can `try/catch` and show a message.
 */
async function api(path, { method = "GET", body, params } = {}) {
  let url = API_BASE + path;
  if (params) {
    const query = new URLSearchParams(params).toString();
    if (query) url += (url.includes("?") ? "&" : "?") + query;
  }

  const options = { method, credentials: "include", headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, options);
  } catch (networkErr) {
    // fetch only rejects on network failure / CORS block, not on HTTP errors.
    const err = new Error(
      "Cannot reach the server. Is the backend running on " + (API_BASE || "this origin") + "?"
    );
    err.status = 0;
    err.cause = networkErr;
    throw err;
  }

  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* some responses (or errors) may have no JSON body */
  }

  if (!res.ok) {
    const message = (data && (data.error || data.message)) || `Request failed (${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/* Thin verb helpers ------------------------------------------------------- */
const http = {
  get: (path, params) => api(path, { params }),
  post: (path, body) => api(path, { method: "POST", body }),
};

/* Auth --------------------------------------------------------------------
 * /api/auth/me always returns 200 with { authenticated, user? }.
 * login / logout throw on failure.
 */
const Auth = {
  me: () => api("/api/auth/me"),
  login: (username, password) =>
    api("/api/auth/login", { method: "POST", body: { username, password } }),
  logout: () => api("/api/auth/logout", { method: "POST" }),
};

/* Where each role lands after login. */
const ROLE_HOME = {
  manager: "manager.html",
  receptionist: "reception.html",
  housekeeping: "housekeeping.html",
};

/**
 * Guard a staff page. Call at the top of a dashboard script.
 * @param {string[]} allowedRoles roles permitted on this page
 * @returns {Promise<object|null>} the logged-in user, or null (after redirect)
 */
async function requireRole(allowedRoles) {
  let session;
  try {
    session = await Auth.me();
  } catch (_) {
    session = { authenticated: false };
  }
  if (!session.authenticated) {
    window.location.href = "login.html";
    return null;
  }
  const user = session.user;
  if (!allowedRoles.includes(user.role)) {
    // Logged in but wrong role -- send them to their own dashboard.
    window.location.href = ROLE_HOME[user.role] || "login.html";
    return null;
  }
  return user;
}
