/* ============================================================
   booking.js -- public guest page (availability, booking, lookup)
   ============================================================ */

const form        = $("#bookingForm");
const roomSelect  = $("#roomSelect");
const roomHint    = $("#roomHint");
const bookingAlert = $("#bookingAlert");
const submitBtn   = $("#submitBtn");

const checkInEl  = form.check_in_date;
const checkOutEl = form.check_out_date;

/* Don't let guests pick dates in the past. */
checkInEl.min = todayISO();
checkOutEl.min = todayISO();

/* --- nights between two YYYY-MM-DD strings ------------------------------- */
function nightsBetween(ci, co) {
  const a = new Date(ci + "T00:00:00");
  const b = new Date(co + "T00:00:00");
  return Math.round((b - a) / 86400000);
}

/* --- refresh the room dropdown whenever both dates are set --------------- */
async function refreshAvailability() {
  const ci = checkInEl.value;
  const co = checkOutEl.value;

  // Keep check-out after check-in in the picker itself.
  if (ci) checkOutEl.min = ci;

  roomSelect.disabled = true;
  roomSelect.innerHTML = "";

  if (!ci || !co) {
    roomSelect.innerHTML = `<option value="">Pick your dates to see availability</option>`;
    roomHint.textContent = "Availability is checked automatically to prevent double-booking.";
    return;
  }
  if (nightsBetween(ci, co) < 1) {
    roomSelect.innerHTML = `<option value="">Check-out must be after check-in</option>`;
    roomHint.textContent = "Choose a check-out date at least one night later.";
    return;
  }

  roomSelect.innerHTML = `<option value="">Checking availability...</option>`;
  try {
    const { rooms } = await http.get("/api/rooms/available", { check_in: ci, check_out: co });
    if (!rooms.length) {
      roomSelect.innerHTML = `<option value="">No rooms available for these dates</option>`;
      roomHint.textContent = "Try different dates -- everything is booked for that range.";
      return;
    }
    roomSelect.innerHTML = `<option value="">Select a room...</option>`;
    for (const r of rooms) {
      const opt = document.createElement("option");
      opt.value = r.room_id;
      opt.textContent = `${r.room_number} -- ${r.room_type} · ${money(r.rate_per_night)} / night`;
      opt.dataset.rate = r.rate_per_night;
      opt.dataset.type = r.room_type;
      opt.dataset.number = r.room_number;
      roomSelect.appendChild(opt);
    }
    roomSelect.disabled = false;
    updateCostHint();
  } catch (err) {
    roomSelect.innerHTML = `<option value="">Could not load availability</option>`;
    roomHint.textContent = err.message;
  }
}

/* --- live cost preview in the hint line ---------------------------------- */
function updateCostHint() {
  const opt = roomSelect.selectedOptions[0];
  const ci = checkInEl.value, co = checkOutEl.value;
  if (!opt || !opt.value || !ci || !co) {
    roomHint.textContent = "Availability is checked automatically to prevent double-booking.";
    return;
  }
  const nights = nightsBetween(ci, co);
  const rate = Number(opt.dataset.rate);
  roomHint.textContent = `${nights} night${nights > 1 ? "s" : ""} × ${money(rate)} = ${money(nights * rate)}`;
}

checkInEl.addEventListener("change", refreshAvailability);
checkOutEl.addEventListener("change", refreshAvailability);
roomSelect.addEventListener("change", updateCostHint);

/* --- submit a booking ---------------------------------------------------- */
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAlert(bookingAlert);

  const payload = {
    full_name: form.full_name.value.trim(),
    email: form.email.value.trim(),
    phone_number: form.phone_number.value.trim(),
    id_number: form.id_number.value.trim(),
    room_id: Number(roomSelect.value),
    check_in_date: checkInEl.value,
    check_out_date: checkOutEl.value,
  };

  if (!payload.full_name || !payload.email || !payload.phone_number) {
    showAlert(bookingAlert, "error", "Please fill in your name, email and phone number.");
    return;
  }
  if (!payload.room_id) {
    showAlert(bookingAlert, "error", "Please choose your dates and pick an available room.");
    return;
  }

  const opt = roomSelect.selectedOptions[0];
  setLoading(submitBtn, true, "Submitting...");
  try {
    const res = await http.post("/api/bookings", payload);
    showConfirmation(res, opt);
    form.reset();
    checkInEl.min = todayISO();
    roomSelect.innerHTML = `<option value="">Pick your dates to see availability</option>`;
    roomSelect.disabled = true;
    roomHint.textContent = "Availability is checked automatically to prevent double-booking.";
  } catch (err) {
    if (err.status === 409) {
      showAlert(bookingAlert, "error", "That room was just taken for those dates. Please pick another.");
      refreshAvailability();
    } else {
      showAlert(bookingAlert, "error", err.message);
    }
  } finally {
    setLoading(submitBtn, false);
  }
});

function showConfirmation(res, opt) {
  const b = res.booking;
  $("#confirmRef").textContent = res.reference;
  const type = opt ? opt.dataset.type : "";
  const num = opt ? opt.dataset.number : "";
  $("#confirmMeta").textContent =
    `Room ${num} · ${type} · ${fmtDate(b.check_in_date)} to ${fmtDate(b.check_out_date)} · ${money(b.cost_total)}`;
  $("#confirmCard").classList.remove("hidden");
  $("#confirmCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
  toast("Booking confirmed -- reference " + res.reference, "success");
}

/* --- look up an existing booking ----------------------------------------- */
const lookupForm   = $("#lookupForm");
const lookupAlert  = $("#lookupAlert");
const lookupResult = $("#lookupResult");
const lookupBtn    = $("#lookupBtn");

lookupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAlert(lookupAlert);
  lookupResult.classList.add("hidden");

  const reference = lookupForm.reference.value.trim();
  const email = lookupForm.email.value.trim();
  if (!reference || !email) {
    showAlert(lookupAlert, "error", "Enter both your reference and the email you booked with.");
    return;
  }

  setLoading(lookupBtn, true, "Checking...");
  try {
    const { booking: b } = await http.get("/api/bookings/lookup", { reference, email });
    lookupResult.innerHTML = `
      <div class="ref-box" style="text-align:left;">
        <div class="row-between" style="margin-bottom:8px;">
          <strong>${esc(b.reference)}</strong>
          ${badge(b.booking_status)}
        </div>
        <div class="muted" style="font-size:.9rem; line-height:1.7;">
          ${esc(b.guest_name)}<br>
          Room ${esc(b.room_number)} · ${esc(b.room_type)}<br>
          ${fmtDate(b.check_in_date)} to ${fmtDate(b.check_out_date)}<br>
          Total ${money(b.cost_total)} · Payment ${badge(b.payment_status)}
        </div>
      </div>`;
    lookupResult.classList.remove("hidden");
  } catch (err) {
    if (err.status === 404) {
      showAlert(lookupAlert, "error", "No matching booking found. Check your reference and email.");
    } else {
      showAlert(lookupAlert, "error", err.message);
    }
  } finally {
    setLoading(lookupBtn, false);
  }
});
