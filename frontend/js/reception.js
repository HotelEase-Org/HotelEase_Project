/* ============================================================
   reception.js -- front desk dashboard
   ============================================================ */

const ROLE_LABEL = { manager: "Manager", receptionist: "Receptionist", housekeeping: "Housekeeping" };

let bookingsCache = [];   // today's arrivals/departures, for search + payment prefill
let allBookingsCache = []; // every booking record (past / present / future)

(async function init() {
  const user = await requireRole(["receptionist", "manager"]);
  if (!user) return;   // guard redirected

  $("#sideUser").textContent = `${user.full_name} · ${ROLE_LABEL[user.role] || user.role}`;
  $("#todayLabel").textContent = fmtDate(todayISO());
  $("#logoutBtn").addEventListener("click", logout);

  wirePaymentForm();
  wireDeskSearch();
  wireTableActions();
  wireRoomActions();
  wireAllBookingsActions();

  await loadAll();
})();

async function logout() {
  try { await Auth.logout(); } catch (_) {}
  window.location.href = "login.html";
}

/* --- load everything ----------------------------------------------------- */
async function loadAll() {
  try {
    const [dash, arrivals, rooms] = await Promise.all([
      http.get("/api/reception/dashboard"),
      http.get("/api/reception/arrivals"),
      http.get("/api/reception/rooms"),
    ]);
    renderKpis(dash, rooms.rooms);
    renderArrivals(arrivals.bookings);
    renderRoomBoard(rooms.rooms);
  } catch (err) {
    showAlert($("#pageAlert"), "error", err.message);
  }
  loadDeletionRequests();
  loadAllBookings();
}

function renderKpis(dash, rooms) {
  const total = rooms.length;
  const occ = dash.rooms_occupied;
  $("#kpiArrivals").textContent = dash.arrivals_today;
  $("#kpiDepartures").textContent = dash.departures_today;
  $("#kpiOccupied").textContent = `${occ} / ${total}`;
  $("#kpiOccPct").textContent = total ? `${Math.round((occ / total) * 100)}% occupancy` : "";
  $("#kpiCleaning").textContent = dash.awaiting_cleaning;
}

/* --- arrivals table ------------------------------------------------------ */
function renderArrivals(bookings) {
  bookingsCache = bookings;
  const body = $("#arrivalsBody");
  if (!bookings.length) {
    body.innerHTML = `<tr><td colspan="5"><div class="empty">No arrivals or departures today.</div></td></tr>`;
    return;
  }
  body.innerHTML = bookings.map((b) => {
    const actions = [];
    if (b.booking_status === "Pending" || b.booking_status === "Confirmed") {
      actions.push(`<button class="btn btn-ghost btn-sm" data-action="checkin" data-id="${b.booking_id}">Check-in</button>`);
    }
    if (b.booking_status === "CheckedIn") {
      actions.push(`<button class="btn btn-ghost btn-sm" data-action="checkout" data-id="${b.booking_id}">Check-out</button>`);
    }
    if (b.payment_status !== "Paid") {
      actions.push(`<button class="btn btn-ghost btn-sm" data-action="pay" data-id="${b.booking_id}">Record Pay</button>`);
    }
    actions.push(`<button class="btn btn-ghost btn-sm" data-action="invoice" data-id="${b.booking_id}">Invoice</button>`);
    actions.push(`<button class="btn btn-danger btn-sm" data-action="reqdelete" data-id="${b.booking_id}">Delete</button>`);
    return `<tr>
      <td class="tab">${esc(b.reference)}</td>
      <td>${esc(b.guest_name)}</td>
      <td>${esc(b.room_number)}</td>
      <td>${badge(b.booking_status)}</td>
      <td>${actions.join(" ") || '<span class="muted">--</span>'}</td>
    </tr>`;
  }).join("");
}

function wireTableActions() {
  $("#arrivalsBody").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const id = btn.dataset.id;
    const action = btn.dataset.action;

    if (action === "pay") { prefillPayment(id); return; }
    if (action === "invoice") { openInvoice(id); return; }
    if (action === "reqdelete") { openDeletionModal(id); return; }

    const b = bookingsCache.find((x) => String(x.booking_id) === String(id));
    const who = b ? `${b.guest_name} (${b.reference})` : "this guest";

    if (action === "checkin") {
      if (!confirm(`Check in ${who}?`)) return;
    } else if (action === "checkout") {
      // Guard against checking out with money still owed (2.2 / 2.3).
      const owes = b && b.payment_status !== "Paid";
      const msg = owes
        ? `${who} still has an outstanding balance (payment is ${b.payment_status}).\n\nCheck out anyway? Record the payment first if it has been settled.`
        : `Check out ${who}? The room will be sent to housekeeping.`;
      if (!confirm(msg)) return;
    }

    setLoading(btn, true, "...");
    try {
      if (action === "checkin") {
        await http.post(`/api/reception/bookings/${id}/check-in`);
        toast("Guest checked in", "success");
      } else if (action === "checkout") {
        await http.post(`/api/reception/bookings/${id}/check-out`);
        toast("Guest checked out -- room sent to cleaning", "success");
      }
      await loadAll();
    } catch (err) {
      toast(err.message, "error");
      setLoading(btn, false);
    }
  });
}

/* --- payment ------------------------------------------------------------- */
function prefillPayment(bookingId) {
  const b = bookingsCache.find((x) => String(x.booking_id) === String(bookingId));
  if (!b) return;
  $("#payBookingId").value = b.booking_id;
  $("#payTarget").textContent = `${b.reference} · ${b.guest_name}`;
  $("#payAmount").value = b.cost_total;
  $("#payBtn").disabled = false;
  clearAlert($("#payAlert"));
  $("#payAmount").focus();
  $("#payForm").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function wirePaymentForm() {
  $("#payForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert($("#payAlert"));
    const bookingId = $("#payBookingId").value;
    const amount = parseMoney($("#payAmount").value);
    const method = $("#payMethod").value;
    if (!bookingId) { showAlert($("#payAlert"), "error", "Pick a booking with \"Record Pay\" first."); return; }
    if (!(amount > 0)) { showAlert($("#payAlert"), "error", "Enter an amount greater than zero."); return; }

    const btn = $("#payBtn");
    setLoading(btn, true, "Recording...");
    try {
      const res = await http.post("/api/reception/payments", {
        booking_id: Number(bookingId), amount, payment_method: method,
      });
      toast(`Payment recorded -- ${res.payment_status}`, "success");
      $("#payForm").reset();
      $("#payBookingId").value = "";
      $("#payTarget").textContent = "select a booking";
      btn.disabled = true;
      await loadAll();
    } catch (err) {
      showAlert($("#payAlert"), "error", err.message);
    } finally {
      setLoading(btn, false);
      if (!$("#payBookingId").value) btn.disabled = true;
    }
  });
}

/* --- desk search (any booking, not just today) --------------------------- */
function wireDeskSearch() {
  const box = $("#deskSearchResult");
  const run = async () => {
    const q = $("#deskSearch").value.trim();
    const btn = $("#deskSearchBtn");
    setLoading(btn, true, "...");
    try {
      const { bookings } = await http.get("/api/reception/bookings", q ? { q } : undefined);
      if (!bookings.length) {
        box.innerHTML = `<div class="empty">No booking matches that reference or name.</div>`;
      } else {
        box.innerHTML = bookings.map((b) => `
          <div class="ref-box" style="text-align:left; margin-bottom:8px;">
            <div class="row-between"><strong>${esc(b.reference)}</strong>${badge(b.booking_status)}</div>
            <div class="muted" style="font-size:.88rem;">
              ${esc(b.guest_name)} · Room ${esc(b.room_number)} · ${fmtDate(b.check_in_date)} to ${fmtDate(b.check_out_date)}<br>
              ${money(b.cost_total)} · ${badge(b.payment_status)}
            </div>
            <div style="margin-top:8px;">
              <button class="btn btn-ghost btn-sm" data-action="invoice" data-id="${b.booking_id}">Invoice</button>
              <button class="btn btn-danger btn-sm" data-action="reqdelete" data-id="${b.booking_id}">Delete</button>
            </div>
          </div>`).join("");
      }
      box.classList.remove("hidden");
    } catch (err) {
      box.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
      box.classList.remove("hidden");
    } finally {
      setLoading(btn, false);
    }
  };
  $("#deskSearchBtn").addEventListener("click", run);
  $("#deskSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); run(); } });
  box.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    if (btn.dataset.action === "invoice") openInvoice(btn.dataset.id);
    else if (btn.dataset.action === "reqdelete") openDeletionModal(btn.dataset.id);
  });
}

/* --- room board ---------------------------------------------------------- */
function renderRoomBoard(rooms) {
  const board = $("#roomBoard");
  if (!rooms.length) { board.innerHTML = `<div class="empty">No rooms configured yet.</div>`; return; }
  board.innerHTML = rooms.map((r) => {
    const canFlag = r.status === "Available" || r.status === "Occupied";
    const flag = canFlag
      ? `<div style="margin-top:8px;"><button class="btn btn-ghost btn-sm" data-action="flag" data-id="${r.room_id}">Flag cleaning</button></div>`
      : "";
    return `<div class="room ${roomTileClass(r.status)}">
      <div class="no">${esc(r.room_number)}</div>
      <div class="type">${esc(r.room_type)}</div>
      ${badge(r.status)}
      ${flag}
    </div>`;
  }).join("");
}

function wireRoomActions() {
  $("#roomBoard").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action='flag']");
    if (!btn) return;
    openAssignModal(btn.dataset.id);
  });
}

/* Pick a housekeeper (or leave unassigned) when sending a room to cleaning. */
async function openAssignModal(roomId) {
  let options = `<option value="">Unassigned (shared cleaning list)</option>`;
  try {
    const { housekeepers } = await http.get("/api/reception/housekeepers");
    options += housekeepers
      .map((h) => `<option value="${esc(h.full_name)}">${esc(h.full_name)}</option>`)
      .join("");
  } catch (_) { /* still allow an unassigned send */ }

  openModal(`
    <h2>Send Room to Cleaning</h2>
    <div class="field">
      <label>Assign to housekeeper</label>
      <select id="assignStaff">${options}</select>
      <div class="hint">Leave unassigned to add it to the shared cleaning list.</div>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn btn-ghost" data-close>Cancel</button>
      <button type="button" class="btn btn-primary" id="assignConfirm">Send to Cleaning</button>
    </div>`);
  $(".modal [data-close]").addEventListener("click", closeModal);
  $("#assignConfirm").addEventListener("click", async () => {
    const assigned_staff = $("#assignStaff").value;
    const btn = $("#assignConfirm");
    setLoading(btn, true, "Sending...");
    try {
      await http.post(`/api/reception/rooms/${roomId}/assign-cleaning`, { assigned_staff });
      closeModal();
      toast(assigned_staff ? `Room sent to ${assigned_staff}` : "Room sent to cleaning", "success");
      await loadAll();
    } catch (err) {
      toast(err.message, "error");
      setLoading(btn, false);
    }
  });
}

/* --- printable invoice (browser print -> PDF, no server storage) --------- */
async function openInvoice(bookingId) {
  let data;
  try {
    data = await http.get(`/api/reception/bookings/${bookingId}/invoice`);
  } catch (err) {
    toast(err.message, "error");
    return;
  }
  const { booking: b, guest: g, room: r, payments, amount_paid, balance_due } = data;
  const nights = Math.max(
    Math.round((new Date(b.check_out_date) - new Date(b.check_in_date)) / 86400000), 1
  );
  const payRows = payments.length
    ? payments.map((p) => `<tr><td>${fmtDate(p.payment_date)}</td><td>${esc(p.payment_method)}</td><td class="r">${money(p.amount)}</td></tr>`).join("")
    : `<tr><td colspan="3" style="color:#777;">No payments recorded yet.</td></tr>`;

  const w = window.open("", "_blank", "width=720,height=900");
  if (!w) { toast("Allow pop-ups to open the printable invoice.", "error"); return; }
  w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Invoice ${esc(b.reference)}</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;color:#1c2230;max-width:680px;margin:24px auto;padding:0 20px;}
    h1{margin:0;font-size:1.5rem;letter-spacing:.5px;} .gold{color:#b8860b;}
    .muted{color:#666;font-size:.85rem;} table{width:100%;border-collapse:collapse;margin:14px 0;}
    th,td{text-align:left;padding:7px 6px;border-bottom:1px solid #e5e5e5;font-size:.9rem;} .r{text-align:right;}
    .totals td{border:none;padding:4px 6px;} .totals .r{font-weight:700;}
    .head{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #b8860b;padding-bottom:10px;}
    .box{background:#f7f7f5;padding:12px 14px;border-radius:8px;margin:14px 0;font-size:.9rem;line-height:1.7;}
    .note{margin-top:18px;font-size:.8rem;color:#777;} @media print{.noprint{display:none;}}
  </style></head><body onload="window.print()">
    <div class="head"><div><h1>Hotel<span class="gold">Ease</span></h1><div class="muted">Booking Invoice</div></div>
      <div style="text-align:right;"><div style="font-weight:700;font-size:1.1rem;">${esc(b.reference)}</div>
      <div class="muted">Status: ${esc(b.booking_status)} · ${esc(b.payment_status)}</div></div></div>
    <div class="box"><strong>${esc(g.full_name)}</strong><br>${esc(g.email)} · ${esc(g.phone_number)}${g.id_number ? "<br>ID: " + esc(g.id_number) : ""}</div>
    <table><thead><tr><th>Description</th><th class="r">Nights</th><th class="r">Rate</th><th class="r">Amount</th></tr></thead>
      <tbody><tr><td>Room ${esc(r.room_number)} -- ${esc(r.room_type)}<br><span class="muted">${fmtDate(b.check_in_date)} to ${fmtDate(b.check_out_date)}</span></td>
      <td class="r">${nights}</td><td class="r">${money(r.rate_per_night)}</td><td class="r">${money(b.cost_total)}</td></tr></tbody></table>
    <h3 style="font-size:1rem;">Payments</h3>
    <table><thead><tr><th>Date</th><th>Method</th><th class="r">Amount</th></tr></thead><tbody>${payRows}</tbody></table>
    <table class="totals"><tr><td>Total</td><td class="r">${money(b.cost_total)}</td></tr>
      <tr><td>Paid</td><td class="r">${money(amount_paid)}</td></tr>
      <tr><td>Balance due</td><td class="r">${money(balance_due)}</td></tr></table>
    <div class="note">Payment is settled in person at reception (cash / Mobile Money). Thank you for staying with HotelEase.</div>
    <div class="noprint" style="margin-top:16px;"><button onclick="window.print()">Print / Save as PDF</button></div>
  </body></html>`);
  w.document.close();
}

/* --- request a booking deletion (needs manager approval) ----------------- */
function openDeletionModal(bookingId) {
  const b = bookingsCache.find((x) => String(x.booking_id) === String(bookingId));
  const who = b ? `${esc(b.reference)} · ${esc(b.guest_name)}` : `booking #${esc(bookingId)}`;
  openModal(`
    <h2>Request Booking Deletion</h2>
    <p class="muted mt0">${who}</p>
    <div id="delAlert" class="alert hidden"></div>
    <div class="field">
      <label for="delReason">Reason for deletion</label>
      <textarea id="delReason" rows="3" placeholder="e.g. Duplicate booking created in error / guest cancelled by phone"></textarea>
      <div class="hint">A manager reviews this. The booking stays until the request is approved.</div>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn btn-ghost" data-close>Cancel</button>
      <button type="button" class="btn btn-danger" id="delConfirm">Submit for Approval</button>
    </div>`);
  $(".modal [data-close]").addEventListener("click", closeModal);
  $("#delConfirm").addEventListener("click", async () => {
    const reason = $("#delReason").value.trim();
    if (reason.length < 5) {
      showAlert($("#delAlert"), "error", "Please give a reason (at least 5 characters).");
      return;
    }
    const btn = $("#delConfirm");
    setLoading(btn, true, "Submitting...");
    try {
      await http.post(`/api/reception/bookings/${bookingId}/deletion-request`, { reason });
      closeModal();
      toast("Deletion request sent to a manager for approval", "success");
      loadDeletionRequests();
    } catch (err) {
      showAlert($("#delAlert"), "error", err.message);
      setLoading(btn, false);
    }
  });
}

async function loadDeletionRequests() {
  const body = $("#deletionsBody");
  if (!body) return;
  try {
    const { deletion_requests: rows } = await http.get("/api/reception/deletion-requests");
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="5"><div class="empty">No deletion requests yet.</div></td></tr>`;
      return;
    }
    body.innerHTML = rows.map((d) => {
      const note = d.review_note
        ? `<div class="muted" style="font-size:.8rem;">${esc(d.reviewed_by_name || "Manager")}: ${esc(d.review_note)}</div>`
        : "";
      return `<tr>
        <td class="tab">${esc(d.booking_reference)}</td>
        <td>${esc(d.guest_name)}</td>
        <td>${esc(d.room_number)}</td>
        <td style="max-width:280px;">${esc(d.reason)}${note}</td>
        <td>${badge(d.status)}</td>
      </tr>`;
    }).join("");
  } catch (err) {
    body.innerHTML = `<tr><td colspan="5"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
}

/* --- all booking records (past / present / future) ----------------------- */
/* Classify a stay against today so the desk can tell records apart at a glance. */
function stayPeriod(b) {
  const today = todayISO();
  if (b.check_out_date < today) return { label: "Past", cls: "muted" };
  if (b.check_in_date > today) return { label: "Upcoming", cls: "prog" };
  return { label: "Current", cls: "busy" };
}

function renderAllBookings(rows) {
  const body = $("#allBookingsBody");
  if (!body) return;
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty">No booking records found.</div></td></tr>`;
    return;
  }
  body.innerHTML = rows.map((b) => {
    const p = stayPeriod(b);
    return `<tr>
      <td class="tab">${esc(b.reference)}</td>
      <td>${esc(b.guest_name)}</td>
      <td>${esc(b.room_number)}</td>
      <td class="muted" style="font-size:.85rem;">
        ${fmtDate(b.check_in_date)} to ${fmtDate(b.check_out_date)}
        <span class="badge ${p.cls}" style="margin-left:4px;">${p.label}</span>
      </td>
      <td>${badge(b.booking_status)}</td>
      <td>${badge(b.payment_status)}</td>
      <td>
        <button class="btn btn-ghost btn-sm" data-action="invoice" data-id="${b.booking_id}">Invoice</button>
        <button class="btn btn-danger btn-sm" data-action="reqdelete" data-id="${b.booking_id}">Delete</button>
      </td>
    </tr>`;
  }).join("");
}

async function loadAllBookings() {
  const body = $("#allBookingsBody");
  if (!body) return;
  try {
    const { bookings } = await http.get("/api/reception/bookings");
    allBookingsCache = bookings;
    applyAllBookingsFilter();
  } catch (err) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
}

/* Client-side filter over the loaded records (reference or guest name). */
function applyAllBookingsFilter() {
  const q = ($("#allSearch")?.value || "").trim().toLowerCase();
  const rows = q
    ? allBookingsCache.filter((b) =>
        (b.reference || "").toLowerCase().includes(q) ||
        (b.guest_name || "").toLowerCase().includes(q))
    : allBookingsCache;
  renderAllBookings(rows);
}

function wireAllBookingsActions() {
  const input = $("#allSearch");
  if (input) input.addEventListener("input", applyAllBookingsFilter);

  const body = $("#allBookingsBody");
  if (!body) return;
  body.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    if (btn.dataset.action === "invoice") openInvoice(btn.dataset.id);
    else if (btn.dataset.action === "reqdelete") openDeletionModal(btn.dataset.id);
  });
}
