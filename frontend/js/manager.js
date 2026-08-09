/* ============================================================
   manager.js -- analytics, staff, room inventory
   ============================================================ */

/* Categorical palette for the donut -- brand gold + steel lead, then well-separated
   hues in fixed order (never cycled). Avoids the reserved status colours. */
const CAT_COLORS = ["#b8860b", "#64748b", "#2f6f9f", "#7c3aed", "#0f766e", "#be5a3c"];
const ROLE_BADGE = { manager: "busy", receptionist: "ok", housekeeping: "warn" };
const MGR_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

(async function init() {
  const user = await requireRole(["manager"]);
  if (!user) return;

  $("#sideUser").textContent = `${user.full_name} · Manager`;
  $("#logoutBtn").addEventListener("click", logout);
  $("#addStaffBtn").addEventListener("click", openStaffModal);
  $("#addRoomBtn").addEventListener("click", openRoomModal);

  await Promise.all([loadAnalytics(), loadStaff(), loadRooms()]);
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
    const body = $("#staffBody");
    if (!staff.length) { body.innerHTML = `<tr><td colspan="3"><div class="empty">No staff accounts yet.</div></td></tr>`; return; }
    body.innerHTML = staff.map((s) => `<tr>
      <td>${esc(s.full_name)}</td>
      <td><span class="badge ${ROLE_BADGE[s.role] || "busy"}">${esc(s.role)}</span></td>
      <td class="muted">${esc(s.username)}</td>
    </tr>`).join("");
  } catch (err) {
    $("#staffBody").innerHTML = `<tr><td colspan="3"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
}

function openStaffModal() {
  openModal(`
    <h2>Add Staff Account</h2>
    <div id="mAlert" class="alert hidden"></div>
    <form id="mStaffForm" novalidate>
      <div class="field"><label>Full Name</label><input name="full_name" required></div>
      <div class="field"><label>Role</label>
        <select name="role"><option value="receptionist">Receptionist</option><option value="housekeeping">Housekeeping</option><option value="manager">Manager</option></select>
      </div>
      <div class="form-row">
        <div class="field"><label>Username</label><input name="username" autocomplete="off" required></div>
        <div class="field"><label>Password</label><input name="password" type="text" autocomplete="off" required></div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" data-close>Cancel</button>
        <button type="submit" class="btn btn-primary" id="mStaffBtn">Create Account</button>
      </div>
    </form>`);
  const form = $("#mStaffForm");
  $(".modal [data-close]").addEventListener("click", closeModal);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert($("#mAlert"));
    const payload = {
      full_name: form.full_name.value.trim(),
      role: form.role.value,
      username: form.username.value.trim(),
      password: form.password.value,
    };
    if (!payload.full_name || !payload.username || !payload.password) {
      showAlert($("#mAlert"), "error", "All fields are required."); return;
    }
    const btn = $("#mStaffBtn");
    setLoading(btn, true, "Creating...");
    try {
      await http.post("/api/manager/staff", payload);
      closeModal();
      toast("Staff account created", "success");
      await loadStaff();
    } catch (err) {
      showAlert($("#mAlert"), "error", err.status === 409 ? "That username is already taken." : err.message);
      setLoading(btn, false);
    }
  });
}

/* --- rooms (aggregated by type, matching the wireframe) ------------------ */
async function loadRooms() {
  try {
    const { rooms } = await http.get("/api/manager/rooms");
    renderRoomInventory(rooms);
  } catch (err) {
    $("#roomBody").innerHTML = `<tr><td colspan="4"><div class="empty">${esc(err.message)}</div></td></tr>`;
  }
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

function openRoomModal() {
  openModal(`
    <h2>Add Room</h2>
    <div id="mAlert" class="alert hidden"></div>
    <form id="mRoomForm" novalidate>
      <div class="form-row">
        <div class="field"><label>Room Number</label><input name="room_number" placeholder="e.g. 104" required></div>
        <div class="field"><label>Room Type</label><input name="room_type" placeholder="e.g. Standard" required></div>
      </div>
      <div class="field"><label>Rate per Night (GH₵)</label><input name="rate_per_night" inputmode="decimal" placeholder="e.g. 450" required></div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" data-close>Cancel</button>
        <button type="submit" class="btn btn-primary" id="mRoomBtn">Add Room</button>
      </div>
    </form>`);
  const form = $("#mRoomForm");
  $(".modal [data-close]").addEventListener("click", closeModal);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert($("#mAlert"));
    const rate = parseFloat(form.rate_per_night.value);
    const payload = {
      room_number: form.room_number.value.trim(),
      room_type: form.room_type.value.trim(),
      rate_per_night: rate,
    };
    if (!payload.room_number || !payload.room_type) { showAlert($("#mAlert"), "error", "Room number and type are required."); return; }
    if (!(rate > 0)) { showAlert($("#mAlert"), "error", "Enter a nightly rate greater than zero."); return; }
    const btn = $("#mRoomBtn");
    setLoading(btn, true, "Adding...");
    try {
      await http.post("/api/manager/rooms", payload);
      closeModal();
      toast("Room added", "success");
      await Promise.all([loadRooms(), loadAnalytics()]);
    } catch (err) {
      showAlert($("#mAlert"), "error", err.status === 409 ? "That room number already exists." : err.message);
      setLoading(btn, false);
    }
  });
}
