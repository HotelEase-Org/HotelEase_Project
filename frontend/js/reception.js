/* ============================================================
   reception.js -- front desk dashboard
   ============================================================ */

const ROLE_LABEL = { manager: "Manager", receptionist: "Receptionist", housekeeping: "Housekeeping" };

let bookingsCache = [];   // today's arrivals/departures, for search + payment prefill

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
    const amount = parseFloat($("#payAmount").value);
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

/* --- desk search (over today's loaded list) ------------------------------ */
function wireDeskSearch() {
  const run = () => {
    const q = $("#deskSearch").value.trim().toLowerCase();
    const box = $("#deskSearchResult");
    if (!q) { box.classList.add("hidden"); return; }
    const hits = bookingsCache.filter(
      (b) => b.reference.toLowerCase().includes(q) || b.guest_name.toLowerCase().includes(q)
    );
    if (!hits.length) {
      box.innerHTML = `<div class="empty">No match in today's arrivals or departures.</div>`;
    } else {
      box.innerHTML = hits.map((b) => `
        <div class="ref-box" style="text-align:left; margin-bottom:8px;">
          <div class="row-between"><strong>${esc(b.reference)}</strong>${badge(b.booking_status)}</div>
          <div class="muted" style="font-size:.88rem;">${esc(b.guest_name)} · Room ${esc(b.room_number)} · ${money(b.cost_total)} · ${badge(b.payment_status)}</div>
        </div>`).join("");
    }
    box.classList.remove("hidden");
  };
  $("#deskSearchBtn").addEventListener("click", run);
  $("#deskSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); run(); } });
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
  $("#roomBoard").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='flag']");
    if (!btn) return;
    setLoading(btn, true, "...");
    try {
      await http.post(`/api/reception/rooms/${btn.dataset.id}/assign-cleaning`);
      toast("Room flagged for cleaning", "success");
      await loadAll();
    } catch (err) {
      toast(err.message, "error");
      setLoading(btn, false);
    }
  });
}
