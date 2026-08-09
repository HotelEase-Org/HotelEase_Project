/* ============================================================
   login.js -- staff sign in, then redirect to the role dashboard
   ============================================================ */

const loginForm  = $("#loginForm");
const loginAlert = $("#loginAlert");
const loginBtn   = $("#loginBtn");

/* Already signed in? Skip the form, go straight to your dashboard. */
(async function redirectIfLoggedIn() {
  try {
    const session = await Auth.me();
    if (session.authenticated) {
      window.location.href = ROLE_HOME[session.user.role] || "index.html";
    }
  } catch (_) {
    /* backend unreachable -- just let them try to log in */
  }
})();

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAlert(loginAlert);

  const username = loginForm.username.value.trim();
  const password = loginForm.password.value;
  if (!username || !password) {
    showAlert(loginAlert, "error", "Enter your username and password.");
    return;
  }

  setLoading(loginBtn, true, "Signing in...");
  try {
    const res = await Auth.login(username, password);
    const role = res.user.role;
    window.location.href = ROLE_HOME[role] || "index.html";
  } catch (err) {
    if (err.status === 401) {
      showAlert(loginAlert, "error", "Invalid username or password.");
    } else {
      showAlert(loginAlert, "error", err.message);
    }
    setLoading(loginBtn, false);
  }
});
