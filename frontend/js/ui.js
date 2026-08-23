/* ============================================================
   ui.js -- shared formatting + UI helpers (no page-specific logic)
   ============================================================ */

/* Tiny DOM helpers -------------------------------------------------------- */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** Escape user/content strings before putting them in innerHTML. */
function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* Formatting -------------------------------------------------------------- */
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

/** 1350 -> "GH₵ 1,350"  (2 decimals only when there are pesewas). */
function money(amount) {
  const n = Number(amount) || 0;
  const hasFraction = Math.round(n * 100) % 100 !== 0;
  const str = n.toLocaleString("en-US", {
    minimumFractionDigits: hasFraction ? 2 : 0,
    maximumFractionDigits: 2,
  });
  return "GH₵ " + str;
}

/** Compact money for KPI tiles: 48200 -> "GH₵ 48.2k". */
function moneyShort(amount) {
  const n = Number(amount) || 0;
  if (Math.abs(n) >= 1000) return "GH₵ " + (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  return money(n);
}

/** "2026-08-25" or ISO datetime -> "25 Aug 2026". Timezone-safe for date-only. */
function fmtDate(value) {
  if (!value) return "--";
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  let y, m, d;
  if (dateOnly) {
    [y, m, d] = value.split("-").map(Number);
  } else {
    const dt = new Date(value);
    if (isNaN(dt)) return "--";
    y = dt.getFullYear(); m = dt.getMonth() + 1; d = dt.getDate();
  }
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

/** ISO datetime -> "25 Aug, 14:20". Returns "--" when absent. */
function fmtDateTime(value) {
  if (!value) return "--";
  const dt = new Date(value);
  if (isNaN(dt)) return "--";
  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  return `${dt.getDate()} ${MONTHS[dt.getMonth()]}, ${hh}:${mm}`;
}

/** "YYYY-MM-DD" for today (local), handy as a date-input min/default. */
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/* Status -> badge --------------------------------------------------------
 * Keyed on the exact strings the backend stores (room / booking / payment).
 */
const STATUS_MAP = {
  // room
  Available:   { cls: "ok",   label: "Available"   },
  Occupied:    { cls: "busy", label: "Occupied"    },
  Cleaning:    { cls: "warn", label: "Cleaning"    },
  InProgress:  { cls: "prog", label: "In Progress" },
  Maintenance: { cls: "crit", label: "Maintenance" },
  // booking
  Pending:     { cls: "warn", label: "Pending"     },
  Confirmed:   { cls: "prog", label: "Confirmed"   },
  CheckedIn:   { cls: "busy", label: "Checked In"  },
  CheckedOut:  { cls: "ok",   label: "Checked Out" },
  // payment
  Unpaid:      { cls: "crit", label: "Unpaid"      },
  Partial:     { cls: "warn", label: "Partial"     },
  Paid:        { cls: "ok",   label: "Paid"        },
};

function badgeMeta(status) {
  return STATUS_MAP[status] || { cls: "busy", label: status || "--" };
}

/** HTML string for a status pill. */
function badge(status) {
  const { cls, label } = badgeMeta(status);
  return `<span class="badge ${cls}">${esc(label)}</span>`;
}

/** Left-accent class for a room tile. */
function roomTileClass(status) {
  return "s-" + badgeMeta(status).cls;
}

/* Inline alerts (inside a container) ------------------------------------- */
function showAlert(container, type, message) {
  if (!container) return;
  container.className = "alert " + type;
  container.innerHTML = esc(message);
  container.classList.remove("hidden");
}
function clearAlert(container) {
  if (!container) return;
  container.classList.add("hidden");
  container.innerHTML = "";
}

/* Toast stack ------------------------------------------------------------- */
function toast(message, type = "info", ms = 3200) {
  let wrap = $(".toast-wrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "toast-wrap";
    document.body.appendChild(wrap);
  }
  const t = document.createElement("div");
  t.className = "toast " + type;
  t.textContent = message;
  wrap.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

/* Button loading state ---------------------------------------------------- */
function setLoading(btn, isLoading, loadingLabel) {
  if (!btn) return;
  if (isLoading) {
    btn.dataset.label = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> ${esc(loadingLabel || "Working...")}`;
  } else {
    btn.disabled = false;
    if (btn.dataset.label !== undefined) {
      btn.innerHTML = btn.dataset.label;
      delete btn.dataset.label;
    }
  }
}

/* Modal ------------------------------------------------------------------- */
function openModal(innerHTML) {
  closeModal();
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `<div class="modal" role="dialog" aria-modal="true">${innerHTML}</div>`;
  backdrop.addEventListener("mousedown", (e) => {
    if (e.target === backdrop) closeModal();
  });
  document.addEventListener("keydown", escToClose);
  document.body.appendChild(backdrop);
  return backdrop;
}
function closeModal() {
  const existing = $(".modal-backdrop");
  if (existing) existing.remove();
  document.removeEventListener("keydown", escToClose);
}
function escToClose(e) {
  if (e.key === "Escape") closeModal();
}
