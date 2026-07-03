const scheduleBody = document.getElementById("scheduleBody");
const statusEl = document.getElementById("status");
const kioskTitleEl = document.getElementById("kioskTitle");
const kioskLogoEl = document.getElementById("kioskLogo");
const eventDateEl = document.getElementById("eventDate");
const remoteInfoEl = document.getElementById("remoteInfo");
const alertOverlay = document.getElementById("alertOverlay");
const alertMessage = document.getElementById("alertMessage");
const alertMeta = document.getElementById("alertMeta");
const dismissAlert = document.getElementById("dismissAlert");
const controlMenu = document.getElementById("controlMenu");
const reloadApp = document.getElementById("reloadApp");
const exitKiosk = document.getElementById("exitKiosk");
const closeMenu = document.getElementById("closeMenu");

const today = new Date();
const todayParam = today.toISOString().slice(0, 10);
const ADMIN_TAP_COUNT = 3;
const ADMIN_TAP_WINDOW_MS = 1500;
const CONTROL_MENU_HOLD_MS = 3000;
let alertTimer = null;
let controlMenuTimer = null;
let adminTapCount = 0;
let adminTapResetTimer = null;

function resolveClockEl() {
  return (
    document.getElementById("controlHotspot") ||
    document.getElementById("clock") ||
    document.querySelector(".kiosk__clock")
  );
}

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
    hour12: true,
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
  const clock = resolveClockEl();
  if (!clock || !eventDateEl) return;
  const now = new Date();
  clock.textContent = now.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
  eventDateEl.textContent = formatDate(todayParam);
}

function setStatus(message) {
  if (statusEl) statusEl.textContent = message;
}

async function loadAppConfig() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("config request failed");
    const config = await response.json();
    if (kioskTitleEl && config.display_title) {
      kioskTitleEl.textContent = config.display_title;
      document.title = config.display_title;
    }
    if (kioskLogoEl) {
      if (config.logo_url) {
        kioskLogoEl.src = config.logo_url;
        kioskLogoEl.hidden = false;
      } else {
        kioskLogoEl.removeAttribute("src");
        kioskLogoEl.hidden = true;
      }
    }
  } catch {
    // The hard-coded title remains usable if config loading fails.
  }
}

function renderNetworkInfo(info) {
  if (!remoteInfoEl) return;
  const url = info.urls?.[0] || info.hotspot_url;
  remoteInfoEl.textContent = url
    ? `Remote admin: ${url}/admin or ${info.mdns_name}:${info.port}/admin`
    : "Remote admin unavailable";
}

async function loadNetworkInfo() {
  try {
    const response = await fetch("/api/network");
    if (!response.ok) throw new Error("network request failed");
    renderNetworkInfo(await response.json());
  } catch {
    if (remoteInfoEl) remoteInfoEl.textContent = "Remote admin unavailable";
  }
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Remote admin still works without offline shell caching.
    });
  }
}

function rowClass(item, nextId) {
  const classes = [`schedule__row--${item.status}`];
  if (item.id === nextId) classes.push("schedule__row--next");
  return classes.join(" ");
}

function formatResult(item) {
  if (item.finish_place != null) {
    const time = item.finish_time ? ` · ${item.finish_time}` : "";
    const category = item.result_category ? ` · ${item.result_category}` : "";
    return `P${item.finish_place}${time}${category}`;
  }
  return formatCountdown(item.countdown_seconds);
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
          <td class="schedule__name">${item.name}</td>
          <td>${formatDate(item.event_date)}</td>
          <td>${formatTime(item.start_time)}</td>
          <td class="schedule__countdown">${formatResult(item)}</td>
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
    setStatus(`Last updated ${new Date().toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    })}`);
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

function resolveAdminBrandTrigger() {
  return (
    document.getElementById("adminBrandTrigger") ||
    document.querySelector(".kiosk__brand")
  );
}

function registerAdminTap() {
  adminTapCount += 1;
  clearTimeout(adminTapResetTimer);
  if (adminTapCount >= ADMIN_TAP_COUNT) {
    adminTapCount = 0;
    window.location.href = "/admin";
    return;
  }
  adminTapResetTimer = setTimeout(() => {
    adminTapCount = 0;
  }, ADMIN_TAP_WINDOW_MS);
}

function configureAdminBrandTrigger() {
  const adminBrandTrigger = resolveAdminBrandTrigger();
  if (!adminBrandTrigger) return;

  adminBrandTrigger.addEventListener("click", registerAdminTap);
}

function configureControlHotspot() {
  const hotspot = resolveClockEl();
  if (!hotspot) return;
  const start = () => {
    clearTimeout(controlMenuTimer);
    controlMenuTimer = setTimeout(showControlMenu, CONTROL_MENU_HOLD_MS);
  };
  const cancel = () => clearTimeout(controlMenuTimer);
  hotspot.addEventListener("pointerdown", start);
  hotspot.addEventListener("pointerup", cancel);
  hotspot.addEventListener("pointerleave", cancel);
}

dismissAlert?.addEventListener("click", hideAlert);
closeMenu?.addEventListener("click", hideControlMenu);
reloadApp?.addEventListener("click", () => window.location.reload());
exitKiosk?.addEventListener("click", closeKioskBrowser);
controlMenu?.addEventListener("click", (event) => {
  if (event.target === controlMenu) hideControlMenu();
});
configureAdminBrandTrigger();
configureControlHotspot();
registerServiceWorker();
loadAppConfig();
updateClock();
loadNetworkInfo();
loadSchedule();
connectAlertStream();
setInterval(updateClock, 1000);
setInterval(loadNetworkInfo, 60000);
setInterval(loadSchedule, 1000);
