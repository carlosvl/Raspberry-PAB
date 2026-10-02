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
let displayDate = [
  today.getFullYear(),
  String(today.getMonth() + 1).padStart(2, "0"),
  String(today.getDate()).padStart(2, "0"),
].join("-");
let kioskNowIso = today.toISOString();
let kioskSimulated = false;
let kioskSimulatedRunning = false;
const ADMIN_TAP_COUNT = 3;
const ADMIN_TAP_WINDOW_MS = 1500;
const CONTROL_MENU_HOLD_MS = 3000;
const ALERT_DISPLAY_MS = 10000;
const ALERT_BATCH_WINDOW_MS = 1000;
let alertTimer = null;
let alertBatchTimer = null;
let alertQueue = [];
let pendingAlertBatch = [];
let alertPlaying = false;
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
    const previousDate = displayDate;
    if (config.display_date) {
      displayDate = config.display_date;
    }
    if (config.display_date && config.display_date !== previousDate) {
      clearAlertQueue();
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
    const theme =
      config.board_theme === "daylight" ? "daylight" : "classic";
    document.documentElement.dataset.boardTheme = theme;
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
// Max frame gap counted as scrolling time, so a stalled tab doesn't jump.
const SCROLL_MAX_DT_MS = 100;
let scrollRaf = null;
let scrollPauseUntil = 0;
let scrollDirection = 1;
let scrollUserIdleTimer = null;
let scrollUserPaused = false;
// Sub-pixel position we own. Reading scrollTop back loses fractions on 1x
// screens (the Pi TV), where a 0.47px step rounds to 0 and never moves.
let scrollPos = 0;
let scrollLastTick = null;

function scheduleNeedsScroll() {
  if (!scheduleScroll) return false;
  return scheduleScroll.scrollHeight > scheduleScroll.clientHeight + 8;
}

function pauseAutoScrollForUser() {
  scrollUserPaused = true;
  clearTimeout(scrollUserIdleTimer);
  scrollUserIdleTimer = setTimeout(() => {
    scrollUserPaused = false;
    // Continue from wherever the user left the list.
    scrollPos = scheduleScroll ? scheduleScroll.scrollTop : 0;
    scrollLastTick = null;
    scrollPauseUntil = performance.now() + SCROLL_PAUSE_MS;
  }, SCROLL_RESUME_IDLE_MS);
}

function tickAutoScroll(now) {
  scrollRaf = requestAnimationFrame(tickAutoScroll);
  const lastTick = scrollLastTick;
  scrollLastTick = now;
  if (!scheduleScroll || scrollUserPaused || !scheduleNeedsScroll()) return;
  if (now < scrollPauseUntil || lastTick == null) return;

  const maxScroll = scheduleScroll.scrollHeight - scheduleScroll.clientHeight;
  if (maxScroll <= 0) return;

  const dt = Math.min(now - lastTick, SCROLL_MAX_DT_MS);
  const next = scrollPos + ((SCROLL_PX_PER_SEC * dt) / 1000) * scrollDirection;

  if (next >= maxScroll) {
    scrollPos = maxScroll;
    scrollDirection = -1;
    scrollPauseUntil = now + SCROLL_PAUSE_MS;
  } else if (next <= 0) {
    scrollPos = 0;
    scrollDirection = 1;
    scrollPauseUntil = now + SCROLL_PAUSE_MS;
  } else {
    scrollPos = next;
  }
  scheduleScroll.scrollTop = Math.round(scrollPos);
}

function startAutoScroll() {
  if (!scheduleScroll) return;
  if (scrollRaf == null) {
    scrollRaf = requestAnimationFrame(tickAutoScroll);
  }
  scrollPos = scheduleScroll.scrollTop;
  scrollLastTick = null;
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

  if (scheduleScroll) {
    // Keep position across 1s refreshes so auto-scroll doesn't jump.
    scheduleScroll.scrollTop = scrollUserPaused ? previousTop : Math.round(scrollPos);
  }
}

const TEAM_STRIP_ROTATE_MS = 6000;
let teamStripSignature = "";
let teamStripTimer = null;

function teamDivisionTitle(label) {
  const [level, division] = String(label || "").split(" ");
  const name = level === "HS" ? "High School" : level === "MS" ? "Middle School" : level;
  return division ? `${name} ${division}` : name;
}

function teamRaceDate(value) {
  const [y, m, d] = String(value || "").split("-").map(Number);
  if (!y || !m || !d) return "";
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function buildTeamCard(bucket) {
  const focus = String(bucket.focus_team || "").trim().toLowerCase();
  const isFocus = (name) => String(name || "").trim().toLowerCase() === focus;
  const chip = (place, name, score, highlight) => `
    <span class="team-chip${highlight ? " team-chip--focus" : ""}">
      <span class="team-chip__place">${place}</span>
      <span class="team-chip__name">${escapeHtml(String(name).replace(/\s+(HS|MS)$/, ""))}</span>
      <span class="team-chip__score">${score}</span>
    </span>`;
  const isToday = String(bucket.race_date) === displayDate;
  const top = bucket.top3 || [];
  const chips = top.map((entry) =>
    chip(entry.place, entry.team_name, entry.score, isFocus(entry.team_name)),
  );
  const focusInTop = top.some((entry) => isFocus(entry.team_name));
  if (!focusInTop && bucket.focus_place != null) {
    chips.push('<span class="team-card__gap" aria-hidden="true">…</span>');
    chips.push(
      chip(bucket.focus_place, bucket.focus_team, bucket.focus_score ?? "", true),
    );
  }
  return `
    <div class="team-card ${isToday ? "team-card--today" : "team-card--past"}">
      <h2 class="team-card__title">${escapeHtml(teamDivisionTitle(bucket.division_label))}<span class="team-card__date">${escapeHtml(teamRaceDate(bucket.race_date))}</span><span class="team-card__tag">${isToday ? "Today" : "Past race"}</span></h2>
      <div class="team-card__chips">${chips.join("")}</div>
    </div>`;
}

function renderTeamTicker(data) {
  const ticker = document.getElementById("kioskTicker");
  const host = document.getElementById("kioskTeams");
  if (!ticker || !host) return;

  // Every race day with results, current day first, then newest past races.
  const buckets = ((data && data.enabled && data.buckets) || [])
    .filter((bucket) => bucket.top3 && bucket.top3.length)
    .sort(
      (a, b) =>
        (String(b.race_date) === displayDate) - (String(a.race_date) === displayDate) ||
        String(b.race_date).localeCompare(String(a.race_date)) ||
        String(a.division_label).localeCompare(String(b.division_label)),
    );

  const signature = JSON.stringify([displayDate, buckets]);
  if (signature === teamStripSignature) return; // don't restart rotation on polls
  teamStripSignature = signature;
  if (teamStripTimer) {
    clearInterval(teamStripTimer);
    teamStripTimer = null;
  }
  if (!buckets.length) {
    ticker.hidden = true;
    host.innerHTML = "";
    return;
  }

  host.innerHTML = buckets.map(buildTeamCard).join("");
  const cards = [...host.querySelectorAll(".team-card")];
  let active = 0;
  cards.forEach((card, i) => card.classList.toggle("team-card--active", i === 0));
  if (cards.length > 1) {
    teamStripTimer = setInterval(() => {
      cards[active].classList.remove("team-card--active");
      active = (active + 1) % cards.length;
      cards[active].classList.add("team-card--active");
    }, TEAM_STRIP_ROTATE_MS);
  }
  ticker.hidden = false;
}

let jamSignature = "";

async function loadSpotifyJam() {
  try {
    const response = await fetch("/api/spotify/jam");
    if (!response.ok) throw new Error("jam request failed");
    const jam = await response.json();
    const panel = document.getElementById("jamPanel");
    const qr = document.getElementById("jamQr");
    if (!panel || !qr) return;
    const signature = jam.active ? String(jam.url) : "";
    if (signature === jamSignature) return;
    jamSignature = signature;
    qr.innerHTML = jam.active ? jam.svg || "" : "";
    panel.hidden = !jam.active;
    panel.parentElement?.classList.toggle("kiosk__footer--jam", Boolean(jam.active));
  } catch {
    // Keep the last state on transient errors.
  }
}

async function loadTeamStandings() {
  try {
    const response = await fetch("/api/team-standings");
    if (!response.ok) throw new Error("team standings request failed");
    const data = await response.json();
    renderTeamTicker(data);
  } catch {
    // Keep last ticker text on transient errors.
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

function clearAlertQueue() {
  alertQueue = [];
  pendingAlertBatch = [];
  alertPlaying = false;
  clearTimeout(alertBatchTimer);
  alertBatchTimer = null;
  clearTimeout(alertTimer);
  alertTimer = null;
  if (alertOverlay) alertOverlay.hidden = true;
}

function displayAlert(alert) {
  if (!alertOverlay || !alertMessage || !alertMeta) return;
  alertMessage.textContent = alert.message;
  alertMeta.textContent = `${alert.name} starts at ${formatTime(alert.start_time)}`;
  alertOverlay.hidden = false;
  if (!alert.sound_enabled) {
    beep();
  }
}

function playNextQueuedAlert() {
  if (!alertQueue.length) {
    alertPlaying = false;
    if (alertOverlay) alertOverlay.hidden = true;
    clearTimeout(alertTimer);
    alertTimer = null;
    return;
  }
  alertPlaying = true;
  const alert = alertQueue.shift();
  displayAlert(alert);
  clearTimeout(alertTimer);
  alertTimer = setTimeout(playNextQueuedAlert, ALERT_DISPLAY_MS);
}

function flushPendingAlertBatch() {
  alertBatchTimer = null;
  if (!pendingAlertBatch.length) return;
  const groups = new Map();
  const order = [];
  for (const alert of pendingAlertBatch) {
    const key = `${alert.rule_id}|${alert.fire_at}`;
    if (!groups.has(key)) {
      groups.set(key, []);
      order.push(key);
    }
    groups.get(key).push(alert);
  }
  pendingAlertBatch = [];
  for (const key of order) {
    alertQueue.push(...groups.get(key));
  }
  if (!alertPlaying) {
    playNextQueuedAlert();
  }
}

function enqueueAlert(alert) {
  pendingAlertBatch.push(alert);
  clearTimeout(alertBatchTimer);
  alertBatchTimer = setTimeout(flushPendingAlertBatch, ALERT_BATCH_WINDOW_MS);
}

function showAlert(alert) {
  enqueueAlert(alert);
}

function hideAlert() {
  clearAlertQueue();
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
    clearAlertQueue();
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
loadTeamStandings();
loadSpotifyJam();
connectAlertStream();
setInterval(async () => {
  await loadAppConfig();
  updateClock();
  updateFfClock();
}, 1000);
setInterval(loadNetworkInfo, 60000);
setInterval(loadSchedule, 1000);
setInterval(loadTeamStandings, 30000);
setInterval(loadSpotifyJam, 10000);
