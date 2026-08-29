const scheduleBody = document.getElementById("scheduleBody");
const scheduleScroll = document.getElementById("scheduleScroll");
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
let displayDate = today.toISOString().slice(0, 10);
let kioskNowIso = today.toISOString();
let kioskSimulated = false;
let kioskSimulatedRunning = false;
const ADMIN_TAP_COUNT = 3;
const ADMIN_TAP_WINDOW_MS = 1500;
const CONTROL_MENU_HOLD_MS = 3000;
let alertTimer = null;
let controlMenuTimer = null;
let adminTapCount = 0;
let adminTapResetTimer = null;
let lastAdminTapActivation = 0;

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
  const date = new Date(`${displayDate}T${timeString}`);
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(date);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
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
  const now = kioskSimulated ? new Date(kioskNowIso) : new Date();
  clock.textContent = now.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
  const dateLabel = formatDate(displayDate);
  eventDateEl.textContent = kioskSimulated
    ? `TEST · ${dateLabel}`
    : dateLabel;
}

function setStatus(message) {
  if (statusEl) statusEl.textContent = message;
}

async function loadAppConfig() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("config request failed");
    const config = await response.json();
    if (config.display_date) {
      displayDate = config.display_date;
    }
    if (config.kiosk_now) {
      kioskNowIso = config.kiosk_now;
    }
    kioskSimulated = Boolean(config.kiosk_simulated);
    kioskSimulatedRunning = Boolean(config.kiosk_simulated_running);
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
    const fontScale = Number(config.board_font_scale);
    if (Number.isFinite(fontScale) && fontScale > 0) {
      document.documentElement.style.setProperty(
        "--board-font-scale",
        String(fontScale / 100)
      );
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

function formatResultCol(item) {
  if (item.finish_place == null) return "";
  const place = String(item.finish_place).padStart(2, "0");
  const parts = [place];
  if (item.finish_time) {
    const time = item.finish_time.replace(/\.\d+$/, "");
    parts.push(time);
  }
  if (item.result_category) parts.push(item.result_category);
  return parts.join(" · ");
}

// Auto-scroll the participant list for unattended TV displays.
const SCROLL_PX_PER_SEC = 28;
const SCROLL_PAUSE_MS = 2200;
const SCROLL_RESUME_IDLE_MS = 8000;
let scrollRaf = null;
let scrollPauseUntil = 0;
let scrollDirection = 1;
let scrollUserIdleTimer = null;
let scrollUserPaused = false;

function scheduleNeedsScroll() {
  if (!scheduleScroll) return false;
  return scheduleScroll.scrollHeight > scheduleScroll.clientHeight + 8;
}

function pauseAutoScrollForUser() {
  scrollUserPaused = true;
  clearTimeout(scrollUserIdleTimer);
  scrollUserIdleTimer = setTimeout(() => {
    scrollUserPaused = false;
    scrollPauseUntil = performance.now() + SCROLL_PAUSE_MS;
  }, SCROLL_RESUME_IDLE_MS);
}

function tickAutoScroll(now) {
  scrollRaf = requestAnimationFrame(tickAutoScroll);
  if (!scheduleScroll || scrollUserPaused || !scheduleNeedsScroll()) return;
  if (now < scrollPauseUntil) return;

  const maxScroll = scheduleScroll.scrollHeight - scheduleScroll.clientHeight;
  if (maxScroll <= 0) return;

  // ~60fps step from px/sec
  const step = (SCROLL_PX_PER_SEC / 60) * scrollDirection;
  let next = scheduleScroll.scrollTop + step;

  if (next >= maxScroll) {
    scheduleScroll.scrollTop = maxScroll;
    scrollDirection = -1;
    scrollPauseUntil = now + SCROLL_PAUSE_MS;
    return;
  }
  if (next <= 0) {
    scheduleScroll.scrollTop = 0;
    scrollDirection = 1;
    scrollPauseUntil = now + SCROLL_PAUSE_MS;
    return;
  }
  scheduleScroll.scrollTop = next;
}

function startAutoScroll() {
  if (!scheduleScroll) return;
  if (scrollRaf == null) {
    scrollRaf = requestAnimationFrame(tickAutoScroll);
  }
  scrollPauseUntil = performance.now() + SCROLL_PAUSE_MS;
  scrollDirection = 1;
}

function configureScheduleScroll() {
  if (!scheduleScroll) return;
  ["wheel", "touchstart", "pointerdown"].forEach((eventName) => {
    scheduleScroll.addEventListener(eventName, pauseAutoScrollForUser, {
      passive: true,
    });
  });
  startAutoScroll();
}

function renderSchedule(items) {
  if (!scheduleBody) return;

  const previousTop = scheduleScroll ? scheduleScroll.scrollTop : 0;

  if (items.length === 0) {
    scheduleBody.innerHTML = '<tr><td colspan="6">No starts scheduled today.</td></tr>';
    return;
  }

  const next = items.find((item) => item.status === "upcoming");
  const nextId = next ? next.id : null;

  scheduleBody.innerHTML = items
    .map(
      (item) => `
        <tr class="${rowClass(item, nextId)}">
          <td class="schedule__name">${escapeHtml(item.name)}</td>
          <td>${escapeHtml(item.race || "")}</td>
          <td>${item.call_up ? escapeHtml(item.call_up) : ""}</td>
          <td>${formatTime(item.start_time)}</td>
          <td class="schedule__countdown">${formatCountdown(item.countdown_seconds)}</td>
          <td class="schedule__result">${formatResultCol(item)}</td>
        </tr>
      `,
    )
    .join("");

  if (scheduleScroll && !scrollUserPaused) {
    // Keep position across 1s refreshes so auto-scroll doesn't jump.
    scheduleScroll.scrollTop = previousTop;
  }
}

async function loadSchedule() {
  try {
    const response = await fetch(`/api/participants?date=${displayDate}`);
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
  if (!alert.sound_enabled) {
    beep();
  }
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

function activateAdminTapOnce() {
  const now = Date.now();
  if (now - lastAdminTapActivation < 250) return;
  lastAdminTapActivation = now;
  registerAdminTap();
}

function configureAdminBrandTrigger() {
  const adminBrandTrigger = resolveAdminBrandTrigger();
  if (!adminBrandTrigger) return;

  const run = () => activateAdminTapOnce();
  adminBrandTrigger.addEventListener("pointerup", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    run();
  });
  adminBrandTrigger.addEventListener("mouseup", (event) => {
    if (event.button !== 0) return;
    run();
  });
  adminBrandTrigger.addEventListener("click", run);
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

// ── Fast-forward toolbar (only when ?testlab=1) ──
const isTestLab = new URLSearchParams(window.location.search).has("testlab");
const ffToolbar = document.getElementById("ffToolbar");
const ffAdvance = document.getElementById("ffAdvance");
const ffBack = document.getElementById("ffBack");
const ffClock = document.getElementById("ffClock");

const FF_HOLD_DELAY_MS = 400;
const FF_HOLD_INTERVAL_MS = 200;
const FF_HOLD_MINUTES = 1;
let ffHoldTimer = null;
let ffHoldInterval = null;

async function advanceClock(minutes) {
  try {
    const response = await fetch("/api/kiosk-clock/advance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutes }),
    });
    if (!response.ok) return;
    const state = await response.json();
    kioskNowIso = state.kiosk_now;
    kioskSimulated = state.simulated;
    kioskSimulatedRunning = state.running;
    displayDate = state.display_date;
    updateClock();
    updateFfClock();
    loadSchedule();
  } catch {
    // Network glitch — the next poll will catch up.
  }
}

function updateFfClock() {
  if (!ffClock) return;
  const now = kioskSimulated ? new Date(kioskNowIso) : new Date();
  ffClock.textContent = now.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

function startFfHold() {
  ffAdvance?.classList.add("is-holding");
  ffHoldTimer = setTimeout(() => {
    ffHoldInterval = setInterval(() => advanceClock(FF_HOLD_MINUTES), FF_HOLD_INTERVAL_MS);
  }, FF_HOLD_DELAY_MS);
}

function stopFfHold() {
  ffAdvance?.classList.remove("is-holding");
  clearTimeout(ffHoldTimer);
  ffHoldTimer = null;
  clearInterval(ffHoldInterval);
  ffHoldInterval = null;
}

function configureFfToolbar() {
  if (!isTestLab || !ffToolbar) return;
  ffToolbar.hidden = false;

  ffAdvance?.addEventListener("click", () => {
    if (!ffHoldInterval) advanceClock(1);
  });
  ffAdvance?.addEventListener("pointerdown", startFfHold);
  ffAdvance?.addEventListener("pointerup", stopFfHold);
  ffAdvance?.addEventListener("pointerleave", stopFfHold);

  ffBack?.addEventListener("click", () => {
    window.location.href = "/admin";
  });
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
configureFfToolbar();
configureScheduleScroll();
registerServiceWorker();
loadAppConfig().then(() => {
  loadSchedule();
  updateFfClock();
});
updateClock();
loadNetworkInfo();
connectAlertStream();
setInterval(async () => {
  await loadAppConfig();
  updateClock();
  updateFfClock();
}, 1000);
setInterval(loadNetworkInfo, 60000);
setInterval(loadSchedule, 1000);
