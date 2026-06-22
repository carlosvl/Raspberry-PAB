const scheduleBody = document.getElementById("scheduleBody");
const statusEl = document.getElementById("status");
const clockEl = document.getElementById("clock");
const eventDateEl = document.getElementById("eventDate");
const alertOverlay = document.getElementById("alertOverlay");
const alertMessage = document.getElementById("alertMessage");
const alertMeta = document.getElementById("alertMeta");
const dismissAlert = document.getElementById("dismissAlert");
const adminHotspot = document.getElementById("adminHotspot");
const controlMenu = document.getElementById("controlMenu");
const reloadApp = document.getElementById("reloadApp");
const exitKiosk = document.getElementById("exitKiosk");
const closeMenu = document.getElementById("closeMenu");

const today = new Date();
const todayParam = today.toISOString().slice(0, 10);
let alertTimer = null;
let adminTimer = null;

function formatDate(dateString) {
  const date = new Date(`${dateString}T00:00:00`);
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(date);
}

function formatTime(timeString) {
  const date = new Date(`${todayParam}T${timeString}`);
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatCountdown(seconds) {
  const sign = seconds < 0 ? "-" : "";
  const remaining = Math.abs(seconds);
  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const secs = remaining % 60;
  return `${sign}${String(hours).padStart(2, "0")}:${String(minutes).padStart(
    2,
    "0",
  )}:${String(secs).padStart(2, "0")}`;
}

function updateClock() {
  if (!clockEl || !eventDateEl) return;
  const now = new Date();
  clockEl.textContent = now.toLocaleTimeString();
  eventDateEl.textContent = formatDate(todayParam);
}

function setStatus(message) {
  if (statusEl) statusEl.textContent = message;
}

function rowClass(item, nextId) {
  const classes = [`schedule__row--${item.status}`];
  if (item.id === nextId) classes.push("schedule__row--next");
  return classes.join(" ");
}

function renderSchedule(items) {
  if (!scheduleBody) return;

  if (items.length === 0) {
    scheduleBody.innerHTML = '<tr><td colspan="4">No starts scheduled today.</td></tr>';
    return;
  }

  const next = items.find((item) => item.status === "upcoming");
  const nextId = next ? next.id : null;

  scheduleBody.innerHTML = items
    .map(
      (item) => `
        <tr class="${rowClass(item, nextId)}">
          <td>${item.name}</td>
          <td>${formatDate(item.event_date)}</td>
          <td>${formatTime(item.start_time)}</td>
          <td class="schedule__countdown">${formatCountdown(item.countdown_seconds)}</td>
        </tr>
      `,
    )
    .join("");
}

async function loadSchedule() {
  try {
    const response = await fetch(`/api/participants?date=${todayParam}`);
    if (!response.ok) throw new Error("schedule request failed");
    const items = await response.json();
    renderSchedule(items);
    setStatus(`Last updated ${new Date().toLocaleTimeString()}`);
  } catch {
    setStatus("Server unavailable");
  }
}

function beep() {
  try {
    const context = new AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = 880;
    gain.gain.setValueAtTime(0.25, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.4);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.4);
  } catch {
    // Audio can be blocked until user interaction; the visual alert still works.
  }
}

function showAlert(alert) {
  if (!alertOverlay || !alertMessage || !alertMeta) return;
  alertMessage.textContent = alert.message;
  alertMeta.textContent = `${alert.name} starts at ${formatTime(alert.start_time)}`;
  alertOverlay.hidden = false;
  beep();
  clearTimeout(alertTimer);
  alertTimer = setTimeout(hideAlert, 10000);
}

function hideAlert() {
  if (alertOverlay) alertOverlay.hidden = true;
  clearTimeout(alertTimer);
}

function showControlMenu() {
  if (controlMenu) controlMenu.hidden = false;
}

function hideControlMenu() {
  if (controlMenu) controlMenu.hidden = true;
}

async function closeKioskBrowser() {
  setStatus("Closing kiosk browser…");
  try {
    await fetch("/api/kiosk/exit-browser", { method: "POST" });
  } catch {
    setStatus("Could not close browser");
  }
}

function connectAlertStream() {
  const source = new EventSource("/api/alerts/stream");
  source.addEventListener("alert", (event) => {
    showAlert(JSON.parse(event.data));
    loadSchedule();
  });
  source.onerror = () => {
    source.close();
    setTimeout(connectAlertStream, 3000);
  };
}

function configureAdminHotspot() {
  if (!adminHotspot) return;
  const start = () => {
    clearTimeout(adminTimer);
    adminTimer = setTimeout(showControlMenu, 3000);
  };
  const cancel = () => clearTimeout(adminTimer);
  adminHotspot.addEventListener("pointerdown", start);
  adminHotspot.addEventListener("pointerup", cancel);
  adminHotspot.addEventListener("pointerleave", cancel);
}

dismissAlert?.addEventListener("click", hideAlert);
closeMenu?.addEventListener("click", hideControlMenu);
reloadApp?.addEventListener("click", () => window.location.reload());
exitKiosk?.addEventListener("click", closeKioskBrowser);
controlMenu?.addEventListener("click", (event) => {
  if (event.target === controlMenu) hideControlMenu();
});
configureAdminHotspot();
updateClock();
loadSchedule();
connectAlertStream();
setInterval(updateClock, 1000);
setInterval(loadSchedule, 1000);
