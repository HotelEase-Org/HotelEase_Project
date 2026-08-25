/* ============================================================
   manager.js -- analytics, staff, room inventory
   ============================================================ */

/* Categorical palette for the donut -- brand gold + steel lead, then well-separated
   hues in fixed order (never cycled). Avoids the reserved status colours. */
const CAT_COLORS = ["#b8860b", "#64748b", "#2f6f9f", "#7c3aed", "#0f766e", "#be5a3c"];
const ROLE_BADGE = { manager: "busy", receptionist: "ok", housekeeping: "warn" };
const MGR_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

let currentUser = null;   // to block deleting your own account
let staffCache = [];      // for prefilling the edit modal
let roomsCache = [];
let allBookingsCache = []; // every booking record, for the monitoring view

(async function init() {
  const user = await requireRole(["manager"]);
  if (!user) return;
  currentUser = user;

  $("#sideUser").textContent = `${user.full_name} · Manager`;
  $("#logoutBtn").addEventListener("click", logout);
  $("#addStaffBtn").addEventListener("click", () => openStaffModal());
  $("#addRoomBtn").addEventListener("click", () => openRoomModal());
  wireStaffActions();
  wireRoomListActions();
  wireDeletionActions();
  wireAllBookingsActions();

  await Promise.all([loadAnalytics(), loadStaff(), loadRooms(), loadDeletions(), loadAllBookings()]);
})();

async function logout() {
  try { await Auth.logout(); } catch (_) {}
  window.location.href = "login.html";
}

/* --- analytics ----------------------------------------------------------- */
async function loadAnalytics() {
  try {
    const a = await http.get("/api/manager/analytics");
    $("#kpiRevenue").textContent = money(a.total_revenue);
    $("#kpiOcc").textContent = `${a.occupancy_rate}%`;
    $("#kpiBookings").textContent = a.total_bookings;
    $("#kpiAov").textContent = a.total_bookings ? money(a.total_revenue / a.total_bookings) : "--";
    renderRevChart(a.revenue_trend);
    renderTypeChart(a.bookings_by_type, a.total_bookings);
  } catch (err) {
    showAlert($("#pageAlert"), "error", err.message);
  }
}

function shortMonth(ym) {
  const [y, m] = ym.split("-").map(Number);
  return `${MGR_MONTHS[m - 1]} '${String(y).slice(2)}`;
}
function shortNum(n) {
  return Math.abs(n) >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(Math.round(n));
}

function renderRevChart(trend) {
  const host = $("#revChart");
  if (!trend || !trend.length) {
    host.innerHTML = `<div class="empty">No revenue recorded yet. Payments will show up here.</div>`;
    return;
  }
  const max = Math.max(...trend.map((t) => t.revenue), 1);
  host.innerHTML = `<div class="bars">${trend.map((t) => {
    const h = Math.max((t.revenue / max) * 100, 2);
    return `<div class="bar-col">
      <div class="bar" style="height:${h}%"><span class="v">${shortNum(t.revenue)}</span></div>
      <div class="x">${esc(shortMonth(t.month))}</div>
    </div>`;
  }).join("")}</div>`;
}

function renderTypeChart(items, total) {
  const host = $("#typeChart");
  if (!items || !items.length || !total) {
    host.innerHTML = `<div class="empty">No bookings yet. The room-type split appears once guests book.</div>`;
    return;
  }
  let start = 0;
  const stops = [];
  const legend = [];
  items.forEach((it, i) => {
    const color = CAT_COLORS[i % CAT_COLORS.length];
    const pct = (it.count / total) * 100;
    const end = i === items.length - 1 ? 100 : start + pct;
    stops.push(`${color} ${start}% ${end}%`);
    legend.push(`<div class="item">
      <span class="swatch" style="background:${color}"></span>
      ${esc(it.room_type)} -- ${it.count} <span class="muted">(${Math.round(pct)}%)</span>
    </div>`);
    start = end;
  });
  host.innerHTML = `
    <div style="display:flex; align-items:center; gap:28px; padding:8px 0; flex-wrap:wrap;">
      <div style="width:150px; height:150px; border-radius:50%; background: conic-gradient(${stops.join(", ")});
                  display:flex; align-items:center; justify-content:center; flex-shrink:0;">
        <div style="width:88px;height:88px;border-radius:50%;background:var(--card);display:flex;flex-direction:column;align-items:center;justify-content:center;">
          <div style="font-weight:800;font-size:1.3rem;">${total}</div>
          <div class="muted" style="font-size:.72rem;">bookings</div>
        </div>
      </div>
      <div class="legend">${legend.join("")}</div>
    </div>`;
}

/* --- staff --------------------------------------------------------------- */
async function loadStaff() {
  try {
    const { staff } = await http.get("/api/manager/staff");
    staffCache = staff;
    const body = $("#staffBody");
    if (!staff.length) { body.innerHTML = `<tr><td colspan="4"><div class="empty">No staff accounts yet.</div></td></tr>`; return; }
    body.innerHTML = staff.map((s) => {
      const isSelf = currentUser && s.staff_id === currentUser.staff_id;
      const del = isSelf ? "" : ` <button class="btn btn-danger btn-sm" data-saction="delete" data-id="${s.staff_id}">Delete</button>`;
      return `<tr>
        <td>${esc(s.full_name)}</td>
        <td><span class="badge ${ROLE_BADGE[s.role] || "busy"}">${esc(s.role)}</span></td>
        <td class="muted">${esc(s.username)}</td>
        <td><button class="btn btn-ghost btn-sm" data-saction="edit" data-id="${s.staff_id}">Edit</button>${del}</td>
      </tr>`;
    }).join("");
  } catch (err) {
    $("#staffBody").innerHTML = `<tr><td colspan="4"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
}

function wireStaffActions() {
  $("#staffBody").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-saction]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const s = staffCache.find((x) => x.staff_id === id);
    if (btn.dataset.saction === "edit") {
      if (s) openStaffModal(s);
    } else if (btn.dataset.saction === "delete") {
      if (!confirm(`Delete the account for ${s ? s.full_name : "this staff member"}? This cannot be undone.`)) return;
      try {
        await http.del(`/api/manager/staff/${id}`);
        toast("Staff account deleted", "success");
        await loadStaff();
      } catch (err) { toast(err.message, "error"); }
    }
  });
}

function openStaffModal(existing) {
  const isEdit = !!existing;
  const roleOpts = ["receptionist", "housekeeping", "manager"].map((r) =>
    `<option value="${r}"${existing && existing.role === r ? " selected" : ""}>${r.charAt(0).toUpperCase() + r.slice(1)}</option>`
  ).join("");
  openModal(`
    <h2>${isEdit ? "Edit Staff Account" : "Add Staff Account"}</h2>
    <div id="mAlert" class="alert hidden"></div>
    <form id="mStaffForm" novalidate>
      <div class="field"><label>Full Name</label><input name="full_name" value="${isEdit ? esc(existing.full_name) : ""}" required></div>
      <div class="field"><label>Role</label><select name="role">${roleOpts}</select></div>
      <div class="form-row">
        <div class="field"><label>Username</label><input name="username" autocomplete="off" value="${isEdit ? esc(existing.username) : ""}" ${isEdit ? "disabled" : "required"}></div>
        <div class="field"><label>Password ${isEdit ? '<span class="muted">(blank = keep)</span>' : ""}</label><input name="password" type="password" autocomplete="new-password" minlength="8" ${isEdit ? "" : "required"}></div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" data-close>Cancel</button>
        <button type="submit" class="btn btn-primary" id="mStaffBtn">${isEdit ? "Save Changes" : "Create Account"}</button>
      </div>
    </form>`);
  const form = $("#mStaffForm");
  $(".modal [data-close]").addEventListener("click", closeModal);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert($("#mAlert"));
    const btn = $("#mStaffBtn");
    if (!form.full_name.value.trim()) { showAlert($("#mAlert"), "error", "Full name is required."); return; }

    if (isEdit) {
      const payload = { full_name: form.full_name.value.trim(), role: form.role.value };
      if (form.password.value) payload.password = form.password.value;
      setLoading(btn, true, "Saving...");
      try {
        await http.patch(`/api/manager/staff/${existing.staff_id}`, payload);
        closeModal(); toast("Staff account updated", "success"); await loadStaff();
      } catch (err) { showAlert($("#mAlert"), "error", err.message); setLoading(btn, false); }
      return;
    }

    const payload = {
      full_name: form.full_name.value.trim(),
      role: form.role.value,
      username: form.username.value.trim(),
      password: form.password.value,
    };
    if (!payload.username || !payload.password) { showAlert($("#mAlert"), "error", "All fields are required."); return; }
    setLoading(btn, true, "Creating...");
    try {
      await http.post("/api/manager/staff", payload);
      closeModal(); toast("Staff account created", "success"); await loadStaff();
    } catch (err) {
      showAlert($("#mAlert"), "error", err.status === 409 ? "That username is already taken." : err.message);
      setLoading(btn, false);
    }
  });
}

/* --- booking deletion requests (approve / reject) ------------------------ */
async function loadDeletions() {
  const body = $("#deletionsBody");
  if (!body) return;
  try {
    const { deletion_requests: rows } = await http.get("/api/manager/deletion-requests");
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="7"><div class="empty">No deletion requests.</div></td></tr>`;
      return;
    }
    body.innerHTML = rows.map((d) => {
      const actions = d.status === "Pending"
        ? `<button class="btn btn-primary btn-sm" data-daction="approve" data-id="${d.request_id}">Approve</button>
           <button class="btn btn-ghost btn-sm" data-daction="reject" data-id="${d.request_id}">Reject</button>`
        : `<span class="muted" style="font-size:.8rem;">by ${esc(d.reviewed_by_name || "--")}</span>`;
      const note = d.review_note
        ? `<div class="muted" style="font-size:.8rem;">Note: ${esc(d.review_note)}</div>`
        : "";
      return `<tr>
        <td class="tab">${esc(d.booking_reference)}</td>
        <td>${esc(d.guest_name)}</td>
        <td>${esc(d.room_number)}</td>
        <td style="max-width:240px;">${esc(d.reason)}${note}</td>
        <td>${esc(d.requested_by_name)}</td>
        <td>${badge(d.status)}</td>
        <td>${actions}</td>
      </tr>`;
    }).join("");
  } catch (err) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
}

function wireDeletionActions() {
  const body = $("#deletionsBody");
  if (!body) return;
  body.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-daction]");
    if (!btn) return;
    const id = btn.dataset.id;
    const action = btn.dataset.daction;

    if (action === "approve") {
      if (!confirm("Approve this deletion? The booking and its payments are permanently removed.")) return;
      setLoading(btn, true, "...");
      try {
        await http.post(`/api/manager/deletion-requests/${id}/approve`);
        toast("Deletion approved -- booking removed", "success");
        await Promise.all([loadDeletions(), loadAnalytics(), loadAllBookings()]);
      } catch (err) { toast(err.message, "error"); setLoading(btn, false); }
    } else if (action === "reject") {
      const note = prompt("Reason for rejecting this request (optional):");
      if (note === null) return;   // cancelled the prompt
      setLoading(btn, true, "...");
      try {
        await http.post(`/api/manager/deletion-requests/${id}/reject`, { note });
        toast("Request rejected -- booking kept", "success");
        await loadDeletions();
      } catch (err) { toast(err.message, "error"); setLoading(btn, false); }
    }
  });
}

/* --- all booking records (read-only monitoring view) --------------------- */
/* Manager reuses the front-desk listing endpoint (manager is in FRONT_DESK). */
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
    body.innerHTML = `<tr><td colspan="6"><div class="empty">No booking records found.</div></td></tr>`;
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
    body.innerHTML = `<tr><td colspan="6"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
}

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
}

/* --- rooms (aggregated by type, matching the wireframe) ------------------ */
async function loadRooms() {
  try {
    const { rooms } = await http.get("/api/manager/rooms");
    roomsCache = rooms;
    renderRoomInventory(rooms);
    renderRoomList(rooms);
  } catch (err) {
    $("#roomBody").innerHTML = `<tr><td colspan="4"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
}

/* Per-room list with edit / delete (below the aggregated inventory). */
function renderRoomList(rooms) {
  const body = $("#roomListBody");
  if (!body) return;
  if (!rooms.length) { body.innerHTML = `<tr><td colspan="5"><div class="empty">No rooms yet.</div></td></tr>`; return; }
  body.innerHTML = rooms.map((r) => `<tr>
    <td class="tab" style="font-weight:700;">${esc(r.room_number)}</td>
    <td>${esc(r.room_type)}</td>
    <td class="tab">${money(r.rate_per_night)}</td>
    <td>${badge(r.status)}</td>
    <td>
      <button class="btn btn-ghost btn-sm" data-raction="edit" data-id="${r.room_id}">Edit</button>
      <button class="btn btn-danger btn-sm" data-raction="delete" data-id="${r.room_id}">Delete</button>
    </td>
  </tr>`).join("");
}

function wireRoomListActions() {
  const body = $("#roomListBody");
  if (!body) return;
  body.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-raction]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    const r = roomsCache.find((x) => x.room_id === id);
    if (btn.dataset.raction === "edit") {
      if (r) openRoomModal(r);
    } else if (btn.dataset.raction === "delete") {
      if (!confirm(`Delete Room ${r ? r.room_number : id}? Rooms with bookings cannot be deleted.`)) return;
      try {
        await http.del(`/api/manager/rooms/${id}`);
        toast("Room deleted", "success");
        await Promise.all([loadRooms(), loadAnalytics()]);
      } catch (err) {
        toast(err.message, "error");
      }
    }
  });
}

function renderRoomInventory(rooms) {
  const body = $("#roomBody");
  if (!rooms.length) { body.innerHTML = `<tr><td colspan="4"><div class="empty">No rooms yet. Add your first room.</div></td></tr>`; return; }

  // Group by type: count, rate (single value or range), occupied count.
  const groups = {};
  for (const r of rooms) {
    const g = groups[r.room_type] || (groups[r.room_type] = { count: 0, occ: 0, rates: new Set() });
    g.count++;
    if (r.status === "Occupied") g.occ++;
    g.rates.add(Number(r.rate_per_night));
  }
  const types = Object.keys(groups).sort();
  let totalCount = 0, totalOcc = 0;
  const rows = types.map((type) => {
    const g = groups[type];
    totalCount += g.count; totalOcc += g.occ;
    const rateList = [...g.rates].sort((a, b) => a - b);
    const rateText = rateList.length === 1 ? money(rateList[0]) : `${money(rateList[0])}–${money(rateList[rateList.length - 1])}`;
    return `<tr>
      <td>${esc(type)}</td>
      <td class="tab">${g.count}</td>
      <td class="tab">${rateText}</td>
      <td class="tab">${g.occ} / ${g.count}</td>
    </tr>`;
  }).join("");
  body.innerHTML = rows + `<tr>
    <td style="font-weight:700;">Total</td>
    <td class="tab" style="font-weight:700;">${totalCount}</td>
    <td class="muted">--</td>
    <td class="tab" style="font-weight:700;">${totalOcc} / ${totalCount}</td>
  </tr>`;
}

function openRoomModal(existing) {
  const isEdit = !!existing;
  const statuses = ["Available", "Cleaning", "InProgress", "Occupied", "Maintenance"];
  const statusField = isEdit ? `
      <div class="field"><label>Status</label><select name="status">
        ${statuses.map((s) => `<option value="${s}"${existing.status === s ? " selected" : ""}>${badgeMeta(s).label}</option>`).join("")}
      </select></div>` : "";
  openModal(`
    <h2>${isEdit ? "Edit Room" : "Add Room"}</h2>
    <div id="mAlert" class="alert hidden"></div>
    <form id="mRoomForm" novalidate>
      <div class="form-row">
        <div class="field"><label>Room Number</label><input name="room_number" placeholder="e.g. 104" value="${isEdit ? esc(existing.room_number) : ""}" required></div>
        <div class="field"><label>Room Type</label><input name="room_type" placeholder="e.g. Standard" value="${isEdit ? esc(existing.room_type) : ""}" required></div>
      </div>
      <div class="field"><label>Rate per Night (GH₵)</label><input name="rate_per_night" inputmode="decimal" placeholder="e.g. 450" value="${isEdit ? existing.rate_per_night : ""}" required></div>
      ${statusField}
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" data-close>Cancel</button>
        <button type="submit" class="btn btn-primary" id="mRoomBtn">${isEdit ? "Save Changes" : "Add Room"}</button>
      </div>
    </form>`);
  const form = $("#mRoomForm");
  $(".modal [data-close]").addEventListener("click", closeModal);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert($("#mAlert"));
    const rate = parseMoney(form.rate_per_night.value);
    const payload = {
      room_number: form.room_number.value.trim(),
      room_type: form.room_type.value.trim(),
      rate_per_night: rate,
    };
    if (isEdit) payload.status = form.status.value;
    if (!payload.room_number || !payload.room_type) { showAlert($("#mAlert"), "error", "Room number and type are required."); return; }
    if (!(rate > 0)) { showAlert($("#mAlert"), "error", "Enter a nightly rate greater than zero."); return; }
    const btn = $("#mRoomBtn");
    setLoading(btn, true, isEdit ? "Saving..." : "Adding...");
    try {
      if (isEdit) await http.patch(`/api/manager/rooms/${existing.room_id}`, payload);
      else await http.post("/api/manager/rooms", payload);
      closeModal();
      toast(isEdit ? "Room updated" : "Room added", "success");
      await Promise.all([loadRooms(), loadAnalytics()]);
    } catch (err) {
      showAlert($("#mAlert"), "error", err.message);
      setLoading(btn, false);
    }
  });
}
