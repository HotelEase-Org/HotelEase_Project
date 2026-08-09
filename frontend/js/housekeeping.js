/* ============================================================
   housekeeping.js -- cleaning work list
   ============================================================ */

const HK_ROLE_LABEL = { manager: "Manager", housekeeping: "Housekeeping" };

(async function init() {
  const user = await requireRole(["housekeeping", "manager"]);
  if (!user) return;

  $("#sideUser").textContent = `${user.full_name} · ${HK_ROLE_LABEL[user.role] || user.role}`;
  $("#logoutBtn").addEventListener("click", logout);
  wireActions();

  await load();
})();

async function logout() {
  try { await Auth.logout(); } catch (_) {}
  window.location.href = "login.html";
}

async function load() {
  try {
    const { rooms } = await http.get("/api/housekeeping/rooms");
    renderKpis(rooms);
    renderTasks(rooms);
  } catch (err) {
    showAlert($("#pageAlert"), "error", err.message);
  }
}

function renderKpis(rooms) {
  $("#kpiClean").textContent = rooms.filter((r) => r.status === "Cleaning").length;
  $("#kpiMaint").textContent = rooms.filter((r) => r.status === "Maintenance").length;
  $("#kpiMine").textContent = rooms.filter((r) => r.assigned_to_me).length;
}

function renderTasks(rooms) {
  const body = $("#taskBody");
  if (!rooms.length) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty">All caught up -- no rooms need attention right now.</div></td></tr>`;
    return;
  }
  body.innerHTML = rooms.map((r) => {
    let action;
    if (r.status === "Cleaning") {
      action = `<button class="btn btn-primary btn-sm" data-action="clean" data-id="${r.room_id}">Mark Clean &#10003;</button>`;
    } else { // Maintenance
      action = `<button class="btn btn-ghost btn-sm" data-action="restore" data-id="${r.room_id}">Back in Service</button>`;
    }
    const flag = r.status === "Cleaning"
      ? ` <button class="btn btn-danger btn-sm" data-action="maintenance" data-id="${r.room_id}">Flag Maintenance</button>`
      : "";
    const mine = r.assigned_to_me ? ` <span class="badge prog">Me</span>` : "";
    return `<tr>
      <td class="tab" style="font-weight:700;">${esc(r.room_number)}</td>
      <td>${esc(r.room_type)}</td>
      <td>${badge(r.status)}</td>
      <td class="muted">${fmtDateTime(r.last_cleaned)}</td>
      <td class="muted">${esc(r.assigned_staff || "--")}${mine}</td>
      <td>${action}${flag}</td>
    </tr>`;
  }).join("");
}

const ACTION_STATUS = { clean: "Available", restore: "Available", maintenance: "Maintenance" };
const ACTION_TOAST = {
  clean: "Room marked clean and available",
  restore: "Room back in service",
  maintenance: "Room flagged for maintenance",
};

function wireActions() {
  $("#taskBody").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    setLoading(btn, true, "...");
    try {
      await http.post(`/api/housekeeping/rooms/${btn.dataset.id}/status`, { status: ACTION_STATUS[action] });
      toast(ACTION_TOAST[action], "success");
      await load();
    } catch (err) {
      toast(err.message, "error");
      setLoading(btn, false);
    }
  });
}
