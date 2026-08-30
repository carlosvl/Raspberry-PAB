const pinPanel = document.getElementById("pinPanel");
const adminHeader = document.getElementById("adminHeader");
const adminNav = document.getElementById("adminNav");
const adminPanels = document.getElementById("adminPanels");
const pinInput = document.getElementById("pinInput");
const savePin = document.getElementById("savePin");
const pinMessage = document.getElementById("pinMessage");
const participantForm = document.getElementById("participantForm");
const participantList = document.getElementById("participantList");
const ruleForm = document.getElementById("ruleForm");
const ruleList = document.getElementById("ruleList");
const adminOutput = document.getElementById("adminOutput");
const adminFooter = document.getElementById("adminFooter");
const remoteInfoEl = document.getElementById("remoteInfo");
const restartServiceButton = document.getElementById("restartService");
const reloadKioskDisplayButton = document.getElementById("reloadKioskDisplay");
const reloadAdminPageButton = document.getElementById("reloadAdminPage");

const TIME_CLOCK_OPTIONS = {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
};

const TIME_DISPLAY_OPTIONS = {
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
};

let cachedRules = [];
let cachedSounds = [];
let musicBreakSoundIds = [];

function localDateParam(now = new Date()) {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const todayParam = localDateParam();

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDisplayTime(timeString, dateString = todayParam) {
  const normalized = String(timeString).slice(0, 5);
  const date = new Date(`${dateString}T${normalized}`);
  if (Number.isNaN(date.getTime())) {
    return timeString;
  }
  return new Intl.DateTimeFormat(undefined, TIME_DISPLAY_OPTIONS).format(date);
}

function formatClock(now = new Date()) {
  return new Intl.DateTimeFormat(undefined, TIME_CLOCK_OPTIONS).format(now);
}

function rgbToHex(red, green, blue) {
  return `#${[red, green, blue]
    .map((value) => Number(value).toString(16).padStart(2, "0"))
    .join("")}`;
}

function parseHexColor(hex) {
  const normalized = hex.replace("#", "");
  return {
    led_red: Number.parseInt(normalized.slice(0, 2), 16),
    led_green: Number.parseInt(normalized.slice(2, 4), 16),
    led_blue: Number.parseInt(normalized.slice(4, 6), 16),
  };
}

function setFieldValue(id, value) {
  const field = document.getElementById(id);
  if (field) field.value = value;
}

function setFieldChecked(id, checked) {
  const field = document.getElementById(id);
  if (field) field.checked = checked;
}

function populateRuleForm(rule) {
  if (!rule) {
    setOutput("Could not load that rule.");
    return;
  }

  try {
    setFieldValue("ruleId", String(rule.id));
    setFieldValue("ruleOffset", String(rule.offset_minutes));
    setFieldValue("ruleMessage", rule.message_template);
    setFieldValue("ruleRepeat", rule.repeat_every_minutes ? String(rule.repeat_every_minutes) : "");
    setFieldChecked("ruleEnabled", rule.enabled);
    setFieldChecked("ruleLedEnabled", rule.led_enabled);
    setFieldValue(
      "ruleLedColor",
      rgbToHex(rule.led_red ?? 255, rule.led_green ?? 200, rule.led_blue ?? 0),
    );
    setFieldValue("ruleLedInterval", String(rule.led_flash_interval_ms ?? 500));
    setFieldValue("ruleLedDuration", String(rule.led_flash_duration_seconds ?? 10));
    setFieldValue("ruleLedChaseDuration", String(rule.led_chase_duration_seconds ?? 10));
    setFieldValue("ruleMatrixEffect", rule.matrix_effect || "solid");
    setFieldChecked("ruleBuzzerEnabled", rule.buzzer_enabled);
    setFieldValue("ruleBuzzerPitch", String(rule.buzzer_pitch_hz ?? 2500));
    setFieldValue("ruleBuzzerVolume", String(rule.buzzer_volume ?? 80));
    setFieldValue("ruleBuzzerCount", String(rule.buzzer_count ?? 3));
    setFieldValue("ruleBuzzerBeepMs", String(rule.buzzer_beep_ms ?? 200));
    setFieldValue("ruleBuzzerGapMs", String(rule.buzzer_gap_ms ?? 150));
    setFieldChecked("ruleSoundEnabled", rule.sound_enabled);
    fillRuleSoundSelect(rule.sound_id ? String(rule.sound_id) : "");
    setFieldValue("ruleSoundVolume", String(rule.sound_volume ?? 80));
    showPanel("rulesPanel");
    const editSection = ruleForm?.querySelector("details.admin-section");
    if (editSection) editSection.open = true;
    ruleForm?.scrollIntoView({ behavior: "smooth", block: "start" });
    setOutput(`Editing rule: ${rule.message_template}`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
}

function readRuleNumber(id, fallback) {
  const parsed = Number(document.getElementById(id)?.value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readRuleLedSettings() {
  const ledColor = parseHexColor(document.getElementById("ruleLedColor").value);
  const effectEl = document.getElementById("ruleMatrixEffect");
  return {
    led_enabled: document.getElementById("ruleLedEnabled").checked,
    led_red: ledColor.led_red,
    led_green: ledColor.led_green,
    led_blue: ledColor.led_blue,
    led_flash_interval_ms: readRuleNumber("ruleLedInterval", 500),
    led_flash_duration_seconds: readRuleNumber("ruleLedDuration", 10),
    led_chase_duration_seconds: readRuleNumber("ruleLedChaseDuration", 10),
    matrix_effect: effectEl?.value || "solid",
  };
}

function readRuleBuzzerSettings() {
  const buzzerEnabledEl = document.getElementById("ruleBuzzerEnabled");
  return {
    buzzer_enabled: buzzerEnabledEl.checked,
    buzzer_pitch_hz: readRuleNumber("ruleBuzzerPitch", 2500),
    buzzer_volume: readRuleNumber("ruleBuzzerVolume", 80),
    buzzer_count: readRuleNumber("ruleBuzzerCount", 3),
    buzzer_beep_ms: readRuleNumber("ruleBuzzerBeepMs", 200),
    buzzer_gap_ms: readRuleNumber("ruleBuzzerGapMs", 150),
  };
}

function readRuleSoundSettings() {
  const soundIdRaw = document.getElementById("ruleSoundId")?.value || "";
  return {
    sound_enabled: document.getElementById("ruleSoundEnabled")?.checked || false,
    sound_id: soundIdRaw ? Number(soundIdRaw) : null,
    sound_volume: readRuleNumber("ruleSoundVolume", 80),
  };
}

function ruleBuzzerSummary(rule) {
  if (!rule.buzzer_enabled) {
    return "";
  }
  return ` · Buzzer ${rule.buzzer_count}x @ ${rule.buzzer_pitch_hz}Hz`;
}

function ruleSoundSummary(rule) {
  if (!rule.sound_enabled || !rule.sound_id) {
    return "";
  }
  const sound = cachedSounds.find((item) => item.id === rule.sound_id);
  const label = sound ? sound.original_name : `#${rule.sound_id}`;
  return ` · HDMI ${label} @ ${rule.sound_volume ?? 80}%`;
}

function ruleLedSummary(rule) {
  if (!rule.led_enabled) {
    return "";
  }
  const color = rgbToHex(rule.led_red, rule.led_green, rule.led_blue);
  const effect = rule.matrix_effect && rule.matrix_effect !== "solid"
    ? ` ${rule.matrix_effect}`
    : "";
  return ` · Matrix ${color}${effect}`;
}
function adminPin() {
  return sessionStorage.getItem("pabAdminPin") || "";
}

function headers(extra = {}) {
  return {
    "Content-Type": "application/json",
    "X-Admin-Pin": adminPin(),
    ...extra,
  };
}

function setOutput(message) {
  if (adminOutput) adminOutput.textContent = message;
}

function setPinMessage(message) {
  if (pinMessage) pinMessage.textContent = message;
}

function setAdminVisible(visible) {
  if (pinPanel) pinPanel.hidden = visible;
  if (adminHeader) adminHeader.hidden = !visible;
  if (adminNav) adminNav.hidden = !visible;
  if (adminPanels) adminPanels.hidden = !visible;
  if (adminFooter) adminFooter.hidden = !visible;
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
      // The admin UI can still run without app-shell caching.
    });
  }
}

function showPanel(targetId) {
  if (!adminPanels) return;
  for (const panel of adminPanels.querySelectorAll(".panel")) {
    panel.hidden = panel.id !== targetId;
  }
  for (const btn of document.querySelectorAll("[data-tab-panel]")) {
    btn.classList.toggle("is-active", btn.dataset.tabPanel === targetId);
  }
  const navKioskLink = adminNav?.querySelector("a[href]");
  if (navKioskLink) {
    navKioskLink.href = targetId === "testLabPanel" ? "/?testlab=1" : "/";
  }
  window.scrollTo({ top: 0 });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: headers(options.headers || {}),
  });
  if (!response.ok) {
    const body = await response.text();
    let msg = body || `Request failed: ${response.status}`;
    try {
      const parsed = JSON.parse(body);
      if (parsed.detail) msg = parsed.detail;
    } catch {
      /* not JSON, use raw text */
    }
    throw new Error(msg);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function verifyPin(pin) {
  const response = await fetch("/api/admin/verify", {
    headers: {
      "X-Admin-Pin": pin,
    },
  });
  return response.ok;
}

function updatePin(value) {
  if (!pinInput) return;
  pinInput.value = value;
}

function appendPinDigit(digit) {
  const nextValue = `${pinInput?.value || ""}${digit}`.slice(0, 12);
  updatePin(nextValue);
  setPinMessage("");
}

let lastPinActivation = { key: "", at: 0 };

function activatePinOnce(key, action) {
  const now = Date.now();
  if (lastPinActivation.key === key && now - lastPinActivation.at < 250) {
    return;
  }
  lastPinActivation = { key, at: now };
  action();
}

function bindPinActivation(button, key, action) {
  if (!button) return;
  const run = () => activatePinOnce(key, action);
  button.addEventListener("pointerup", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    run();
  });
  button.addEventListener("mouseup", (event) => {
    if (event.button !== 0) return;
    run();
  });
  button.addEventListener("click", () => {
    run();
  });
}

function deletePinDigit() {
  updatePin((pinInput?.value || "").slice(0, -1));
}

function clearPinDigits() {
  updatePin("");
  setPinMessage("");
}

async function openKeyboard() {
  setPinMessage("Opening keyboard...");
  try {
    const response = await fetch("/api/kiosk/keyboard", { method: "POST" });
    if (!response.ok) throw new Error("keyboard request failed");
    setPinMessage("Keyboard opened.");
    setOutput("Keyboard opened.");
  } catch (error) {
    setPinMessage("Keyboard is not available on this display.");
    setOutput("Keyboard is not available on this display.");
  }
}

async function reloadKioskDisplay() {
  setOutput("Reloading HDMI kiosk display...");
  if (reloadKioskDisplayButton) reloadKioskDisplayButton.disabled = true;
  try {
    await api("/api/kiosk/reload-display", { method: "POST" });
    setOutput("Kiosk display reload sent. The board should refresh in a few seconds.");
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  } finally {
    if (reloadKioskDisplayButton) reloadKioskDisplayButton.disabled = false;
  }
}

async function hardReloadAdminPage() {
  setOutput("Reloading admin page...");
  if ("serviceWorker" in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((registration) => registration.unregister()));
  }
  if ("caches" in window) {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
  }
  window.location.reload();
}

async function restartService() {
  if (
    !window.confirm(
      "Restart the Raspberry-PAB service? The page may disconnect briefly.",
    )
  ) {
    return;
  }

  setOutput("Restarting service...");
  if (restartServiceButton) restartServiceButton.disabled = true;
  try {
    await api("/api/kiosk/restart-service", { method: "POST" });
  } catch {
    // The connection often drops while systemd restarts the app.
  }

  setOutput("Waiting for service to come back...");
  try {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      await new Promise((resolve) => {
        setTimeout(resolve, 2000);
      });
      try {
        const response = await fetch("/api/health");
        if (response.ok) {
          setOutput("Service restarted.");
          await loadAll();
          return;
        }
      } catch {
        // Service is still restarting.
      }
    }
    setOutput("Restart requested. Reload the page if the admin UI does not recover.");
  } finally {
    if (restartServiceButton) restartServiceButton.disabled = false;
  }
}

async function revealAdmin() {
  setAdminVisible(true);
  showPanel("participantsPanel");
  await Promise.all([loadNetworkInfo(), loadAll()]);
}

async function unlock() {
  const pin = pinInput?.value || "";
  if (!pin) return;
  setPinMessage("Checking PIN...");
  if (!(await verifyPin(pin))) {
    sessionStorage.removeItem("pabAdminPin");
    setAdminVisible(false);
    setPinMessage("Invalid PIN.");
    return;
  }
  sessionStorage.setItem("pabAdminPin", pin);
  setPinMessage("");
  await revealAdmin();
}

function clearParticipantForm() {
  document.getElementById("participantId").value = "";
  document.getElementById("participantName").value = "";
  const raceEl = document.getElementById("participantRace");
  if (raceEl) raceEl.value = "";
  const callUpEl = document.getElementById("participantCallUp");
  if (callUpEl) callUpEl.value = "";
  document.getElementById("participantDate").value = todayParam;
  document.getElementById("participantTime").value = "";
}

function clearRuleForm() {
  document.getElementById("ruleId").value = "";
  document.getElementById("ruleOffset").value = "";
  document.getElementById("ruleMessage").value = "";
  document.getElementById("ruleRepeat").value = "";
  document.getElementById("ruleEnabled").checked = true;
  document.getElementById("ruleLedEnabled").checked = false;
  document.getElementById("ruleLedColor").value = "#ffc800";
  document.getElementById("ruleLedInterval").value = "500";
  document.getElementById("ruleLedDuration").value = "10";
  document.getElementById("ruleLedChaseDuration").value = "10";
  const matrixEffectEl = document.getElementById("ruleMatrixEffect");
  if (matrixEffectEl) matrixEffectEl.value = "solid";
  document.getElementById("ruleBuzzerEnabled").checked = false;
  document.getElementById("ruleBuzzerPitch").value = "2500";
  document.getElementById("ruleBuzzerVolume").value = "80";
  document.getElementById("ruleBuzzerCount").value = "3";
  document.getElementById("ruleBuzzerBeepMs").value = "200";
  document.getElementById("ruleBuzzerGapMs").value = "150";
  const soundEnabledEl = document.getElementById("ruleSoundEnabled");
  if (soundEnabledEl) soundEnabledEl.checked = false;
  const soundIdEl = document.getElementById("ruleSoundId");
  if (soundIdEl) soundIdEl.value = "";
  const soundVolumeEl = document.getElementById("ruleSoundVolume");
  if (soundVolumeEl) soundVolumeEl.value = "80";
}

async function loadParticipants() {
  const date = document.getElementById("participantDate").value || todayParam;
  const participants = await api(`/api/participants?date=${date}`, {
    headers: { "X-Admin-Pin": adminPin() },
  });
  if (!participantList) return;
  participantList.innerHTML = participants
    .map(
      (item) => `
        <div class="admin__item">
          <div class="admin__item-main">
            <strong>${escapeHtml(item.name)}</strong>
            <span>${escapeHtml(item.race || "—")} · Call up ${item.call_up ? escapeHtml(item.call_up) : "—"} · Start ${escapeHtml(formatDisplayTime(item.start_time, item.event_date))}</span>
          </div>
          <button data-edit-participant="${item.id}" type="button">Edit</button>
          <button data-delete-participant="${item.id}" type="button">Delete</button>
        </div>
      `,
    )
    .join("");

  participantList.querySelectorAll("[data-edit-participant]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = participants.find(
        (participant) => String(participant.id) === String(button.dataset.editParticipant),
      );
      if (!item) return;
      document.getElementById("participantId").value = item.id;
      document.getElementById("participantName").value = item.name;
      const raceEl = document.getElementById("participantRace");
      if (raceEl) raceEl.value = item.race || "";
      const callUpEl = document.getElementById("participantCallUp");
      if (callUpEl) {
        callUpEl.value = item.call_up ? String(item.call_up) : "";
      }
      document.getElementById("participantDate").value = item.event_date;
      document.getElementById("participantTime").value = item.start_time.slice(0, 5);
      participantForm?.scrollIntoView({ behavior: "smooth", block: "start" });
      setOutput(`Editing participant: ${item.name}`);
    });
  });

  participantList.querySelectorAll("[data-delete-participant]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/participants/${button.dataset.deleteParticipant}`, {
        method: "DELETE",
      });
      await loadParticipants();
    });
  });
}

async function loadRules() {
  const rules = await api("/api/reminder-rules", {
    headers: { "X-Admin-Pin": adminPin() },
  });
  cachedRules = rules;
  if (!ruleList) return;
  ruleList.innerHTML = rules
    .map(
      (rule) => {
        const color = rule.led_enabled
          ? rgbToHex(rule.led_red ?? 255, rule.led_green ?? 200, rule.led_blue ?? 0)
          : null;
        const swatch = color
          ? `<span class="rule-color-swatch" style="--swatch:${color}" title="${escapeHtml(color)}"></span>`
          : "";
        return `
        <div class="admin__item">
          <div class="admin__item-main">
            <strong>${swatch}${escapeHtml(rule.offset_minutes)} min: ${escapeHtml(rule.message_template)}</strong>
            <span>${rule.repeat_every_minutes ? `Repeats every ${escapeHtml(rule.repeat_every_minutes)} min` : "One time"} · ${rule.enabled ? "Enabled" : "Disabled"}${escapeHtml(ruleLedSummary(rule))}${escapeHtml(ruleBuzzerSummary(rule))}${escapeHtml(ruleSoundSummary(rule))}</span>
          </div>
          <button data-edit-rule="${rule.id}" type="button">Edit</button>
          <button data-delete-rule="${rule.id}" type="button">Delete</button>
        </div>
      `;
      },
    )
    .join("");
}

function fillRuleSoundSelect(selectedId) {
  const select = document.getElementById("ruleSoundId");
  if (!select) return;
  const current = selectedId !== undefined ? selectedId : select.value;
  select.innerHTML =
    `<option value="">— none —</option>` +
    cachedSounds
      .map(
        (sound) =>
          `<option value="${sound.id}">${escapeHtml(sound.original_name)} (${Math.round(sound.size_bytes / 1024)} KB)</option>`,
      )
      .join("");
  if (current) {
    select.value = String(current);
  }
}

function formatSoundSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function loadSounds() {
  const sounds = await api("/api/admin/sounds");
  cachedSounds = sounds;
  fillRuleSoundSelect();
  fillMusicBreakAddSelect();
  const soundList = document.getElementById("soundList");
  if (!soundList) return;
  if (!sounds.length) {
    soundList.innerHTML = `<p class="branding__hint">No sounds uploaded yet.</p>`;
    return;
  }
  soundList.innerHTML = sounds
    .map(
      (sound) => `
        <div class="admin__item">
          <div class="admin__item-main">
            <strong>${escapeHtml(sound.original_name)}</strong>
            <span>${escapeHtml(formatSoundSize(sound.size_bytes))} · ${escapeHtml(sound.content_type)}</span>
          </div>
          <button data-test-sound="${sound.id}" type="button">Test</button>
          <button data-delete-sound="${sound.id}" type="button">Delete</button>
        </div>
      `,
    )
    .join("");

  soundList.querySelectorAll("[data-test-sound]").forEach((button) => {
    button.addEventListener("click", async () => {
      const soundId = button.dataset.testSound;
      setOutput("Testing HDMI sound...");
      try {
        await api(`/api/admin/sounds/${soundId}/test`, {
          method: "POST",
          body: JSON.stringify({ volume: 80 }),
        });
        setOutput("HDMI sound test started.");
      } catch (error) {
        setOutput(error instanceof Error ? error.message : String(error));
      }
    });
  });

  soundList.querySelectorAll("[data-delete-sound]").forEach((button) => {
    button.addEventListener("click", async () => {
      const soundId = button.dataset.deleteSound;
      try {
        await api(`/api/admin/sounds/${soundId}`, { method: "DELETE" });
        await loadSounds();
        await loadMusicBreaks();
        await loadRules();
        setOutput("Sound deleted.");
      } catch (error) {
        setOutput(error instanceof Error ? error.message : String(error));
      }
    });
  });
}

function soundNameById(soundId) {
  const match = (cachedSounds || []).find((sound) => Number(sound.id) === Number(soundId));
  return match ? match.original_name : `Sound #${soundId}`;
}

function fillMusicBreakAddSelect() {
  const select = document.getElementById("musicBreakAddSound");
  if (!select) return;
  const options = (cachedSounds || [])
    .map(
      (sound) =>
        `<option value="${sound.id}">${escapeHtml(sound.original_name)}</option>`,
    )
    .join("");
  select.innerHTML = options || `<option value="">No sounds uploaded</option>`;
}

function renderMusicBreakPlaylist() {
  const list = document.getElementById("musicBreakPlaylist");
  if (!list) return;
  if (!musicBreakSoundIds.length) {
    list.innerHTML = `<p class="branding__hint">Playlist empty — add sounds above.</p>`;
    return;
  }
  list.innerHTML = musicBreakSoundIds
    .map(
      (soundId, index) => `
        <div class="admin__item">
          <div class="admin__item-main">
            <strong>${index + 1}. ${escapeHtml(soundNameById(soundId))}</strong>
          </div>
          <button data-music-up="${index}" type="button" ${index === 0 ? "disabled" : ""}>Up</button>
          <button data-music-down="${index}" type="button" ${
            index === musicBreakSoundIds.length - 1 ? "disabled" : ""
          }>Down</button>
          <button data-music-remove="${index}" type="button">Remove</button>
        </div>
      `,
    )
    .join("");

  list.querySelectorAll("[data-music-up]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.musicUp);
      if (index <= 0) return;
      const swap = musicBreakSoundIds[index - 1];
      musicBreakSoundIds[index - 1] = musicBreakSoundIds[index];
      musicBreakSoundIds[index] = swap;
      renderMusicBreakPlaylist();
    });
  });
  list.querySelectorAll("[data-music-down]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.musicDown);
      if (index >= musicBreakSoundIds.length - 1) return;
      const swap = musicBreakSoundIds[index + 1];
      musicBreakSoundIds[index + 1] = musicBreakSoundIds[index];
      musicBreakSoundIds[index] = swap;
      renderMusicBreakPlaylist();
    });
  });
  list.querySelectorAll("[data-music-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.musicRemove);
      musicBreakSoundIds.splice(index, 1);
      renderMusicBreakPlaylist();
    });
  });
}

function formatMusicBreakStatus(status) {
  const parts = [];
  parts.push(status.enabled ? "ON" : "OFF");
  if (status.playing) parts.push("playing now");
  if (status.next_at) {
    const when = new Date(status.next_at);
    parts.push(
      `next ${when.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
      })} (#${status.next_slot}, ${soundNameById(status.next_sound_id)})`,
    );
  } else if (status.enabled) {
    parts.push("no upcoming slot");
  }
  return `Status: ${parts.join(" · ")}`;
}

async function loadMusicBreaks() {
  const status = await api("/api/admin/music-breaks");
  musicBreakSoundIds = Array.isArray(status.sound_ids)
    ? status.sound_ids.map(Number)
    : [];
  const enabled = document.getElementById("musicBreakEnabled");
  const start = document.getElementById("musicBreakStart");
  const interval = document.getElementById("musicBreakInterval");
  const volume = document.getElementById("musicBreakVolume");
  const pulse = document.getElementById("musicBreakPulse");
  const statusEl = document.getElementById("musicBreakStatus");
  if (enabled) enabled.checked = Boolean(status.enabled);
  if (start && status.start_time) start.value = status.start_time;
  if (interval) interval.value = String(status.interval_minutes ?? 15);
  if (volume) volume.value = String(status.volume ?? 80);
  if (pulse) pulse.value = String(status.pulse_ms ?? 500);
  if (statusEl) statusEl.textContent = formatMusicBreakStatus(status);
  fillMusicBreakAddSelect();
  renderMusicBreakPlaylist();
}

async function saveMusicBreaks() {
  const body = {
    enabled: Boolean(document.getElementById("musicBreakEnabled")?.checked),
    start_time: document.getElementById("musicBreakStart")?.value || "09:00",
    interval_minutes: Number(document.getElementById("musicBreakInterval")?.value || 15),
    volume: Number(document.getElementById("musicBreakVolume")?.value || 80),
    pulse_ms: Number(document.getElementById("musicBreakPulse")?.value || 500),
    sound_ids: musicBreakSoundIds.map(Number),
  };
  const status = await api("/api/admin/music-breaks", {
    method: "PUT",
    body: JSON.stringify(body),
  });
  musicBreakSoundIds = Array.isArray(status.sound_ids)
    ? status.sound_ids.map(Number)
    : [];
  const statusEl = document.getElementById("musicBreakStatus");
  if (statusEl) statusEl.textContent = formatMusicBreakStatus(status);
  renderMusicBreakPlaylist();
  setOutput("Music breaks saved.");
}

function configureMusicBreaks() {
  document.getElementById("musicBreakForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await saveMusicBreaks();
    } catch (error) {
      setOutput(error instanceof Error ? error.message : String(error));
    }
  });
  document.getElementById("musicBreakAdd")?.addEventListener("click", () => {
    const select = document.getElementById("musicBreakAddSound");
    const soundId = Number(select?.value);
    if (!Number.isFinite(soundId) || soundId <= 0) {
      setOutput("Upload a sound first.");
      return;
    }
    musicBreakSoundIds.push(soundId);
    renderMusicBreakPlaylist();
  });
  document.getElementById("musicBreakTest")?.addEventListener("click", async () => {
    setOutput("Testing music break…");
    try {
      await saveMusicBreaks();
      const status = await api("/api/admin/music-breaks/test", { method: "POST" });
      const statusEl = document.getElementById("musicBreakStatus");
      if (statusEl) statusEl.textContent = formatMusicBreakStatus(status);
      setOutput("Music break test finished.");
    } catch (error) {
      setOutput(error instanceof Error ? error.message : String(error));
    }
  });
  document.getElementById("musicBreakStop")?.addEventListener("click", async () => {
    try {
      const status = await api("/api/admin/music-breaks/stop", { method: "POST" });
      const statusEl = document.getElementById("musicBreakStatus");
      if (statusEl) statusEl.textContent = formatMusicBreakStatus(status);
      setOutput("Music break stopped.");
    } catch (error) {
      setOutput(error instanceof Error ? error.message : String(error));
    }
  });
}

async function uploadSoundFile() {
  const input = document.getElementById("soundUpload");
  const statusEl = document.getElementById("soundUploadStatus");
  const file = input?.files?.[0];
  if (!file) {
    if (statusEl) statusEl.textContent = "Choose a sound file first.";
    return;
  }
  if (statusEl) statusEl.textContent = "Uploading…";
  const formData = new FormData();
  formData.append("file", file);
  try {
    const response = await fetch("/api/admin/sounds", {
      method: "POST",
      headers: { "X-Admin-Pin": adminPin() },
      body: formData,
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Upload failed (${response.status})`);
    }
    const sound = await response.json();
    if (input) input.value = "";
    if (statusEl) statusEl.textContent = `Uploaded ${sound.original_name}.`;
    await loadSounds();
    await loadMusicBreaks();
    setOutput(`Uploaded sound: ${sound.original_name}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (statusEl) statusEl.textContent = message;
    setOutput(message);
  }
}

async function loadRaceResults() {
  const raceResultsList = document.getElementById("raceResultsList");
  const dateInput = document.getElementById("raceResultsDate");
  if (!raceResultsList || !dateInput) return;
  const date = dateInput.value || todayParam;
  const rows = await api(`/api/admin/race-results?date=${date}`, {
    headers: { "X-Admin-Pin": adminPin() },
  });
  if (rows.length === 0) {
    raceResultsList.innerHTML = "<p>No participants for this date.</p>";
    return;
  }
  raceResultsList.innerHTML = rows
    .map((row) => {
      const result =
        row.match_state === "matched"
          ? `P${row.place} · ${escapeHtml(row.total_time || "")} · ${escapeHtml(row.category_label || "")}`
          : row.match_state;
      const link = row.results_url
        ? `<a href="${escapeHtml(row.results_url)}" target="_blank" rel="noreferrer">IYR</a>`
        : "";
      return `
        <div class="admin__item">
          <div class="admin__item-main">
            <strong>${escapeHtml(row.participant_name)}</strong>
            <span>${escapeHtml(row.start_time.slice(0, 5))} · ${escapeHtml(result)} · ${escapeHtml(row.venue_label || "No venue")} ${link}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

let DEFAULT_SIM_TIME = "2025-08-23T10:25";
let currentScenario = null;

async function loadKioskClockStatus() {
  const statusEl = document.getElementById("kioskClockStatus");
  const input = document.getElementById("kioskSimDateTime");
  if (!statusEl) return;
  try {
    const clock = await api("/api/admin/kiosk-clock", {
      headers: { "X-Admin-Pin": adminPin() },
    });
    if (input) {
      input.value = clock.simulated
        ? clock.kiosk_now.slice(0, 16)
        : DEFAULT_SIM_TIME;
    }
    statusEl.textContent = clock.simulated
      ? `Kiosk clock: TEST ${clock.kiosk_now}${clock.running ? " (running)" : " (paused)"}`
      : "Kiosk clock: real time";
  } catch (error) {
    statusEl.textContent = error instanceof Error ? error.message : String(error);
  }
}

async function loadAll() {
  try {
    await Promise.all([
      loadBranding(),
      loadSystemClock({ fillFields: true }).catch((error) => {
        const status = document.getElementById("systemClockStatus");
        if (status) {
          status.textContent =
            error instanceof Error ? error.message : "Could not load Pi clock";
        }
      }),
      loadTouchConfig(),
      loadParticipants(),
      loadSounds(),
      loadMusicBreaks(),
      loadRules(),
      loadRaceResults(),
      loadKioskClockStatus(),
      loadScenarioList(),
      loadSyncInterval(),
      loadHardwareStatus(),
      loadLedConfig(),
      loadMatrixStatus(),
      loadWifiPanel(),
    ]);
    setOutput("Loaded.");
  } catch (error) {
    setOutput(error.message);
  }
}

function fillWifiConnectForm(ssid, preferPasswordFocus = false) {
  const ssidInput = document.getElementById("wifiSsid");
  const passwordInput = document.getElementById("wifiPassword");
  if (ssidInput) ssidInput.value = ssid || "";
  if (passwordInput) passwordInput.value = "";
  if (preferPasswordFocus && passwordInput) {
    passwordInput.focus();
  } else if (ssidInput) {
    ssidInput.focus();
  }
}

const WIFI_KB_LAYERS = {
  lower: [
    { rowClass: "", keys: "1234567890".split("") },
    { rowClass: "", keys: "qwertyuiop".split("") },
    { rowClass: "wifi-keyboard__row--9", keys: "asdfghjkl".split("") },
    { rowClass: "wifi-keyboard__row--7", keys: "zxcvbnm".split("") },
  ],
  upper: [
    { rowClass: "", keys: "1234567890".split("") },
    { rowClass: "", keys: "QWERTYUIOP".split("") },
    { rowClass: "wifi-keyboard__row--9", keys: "ASDFGHJKL".split("") },
    { rowClass: "wifi-keyboard__row--7", keys: "ZXCVBNM".split("") },
  ],
  symbols: [
    { rowClass: "", keys: "!@#$%^&*()".split("") },
    { rowClass: "", keys: "-_=+[]{}\\".split("") },
    { rowClass: "wifi-keyboard__row--9", keys: ";:'\",.<>?".split("") },
    { rowClass: "wifi-keyboard__row--7", keys: ["~", "`", "/", "|", "#", "@", "$"] },
  ],
};

let wifiKeyboardTargetId = "wifiSsid";
let wifiKeyboardShifted = false;
let wifiKeyboardSymbols = false;

function wifiKeyboardTargetInput() {
  return document.getElementById(wifiKeyboardTargetId);
}

function updateWifiKeyboardTargetLabel() {
  const label = document.getElementById("wifiKeyboardTarget");
  const name = wifiKeyboardTargetId === "wifiPassword" ? "Password" : "SSID";
  if (label) label.textContent = `Typing into: ${name}`;
  document.querySelectorAll("[data-wifi-kb-target]").forEach((button) => {
    button.classList.toggle(
      "is-active",
      button.getAttribute("data-wifi-kb-target") === wifiKeyboardTargetId,
    );
  });
}

function currentWifiKeyboardLayer() {
  if (wifiKeyboardSymbols) return WIFI_KB_LAYERS.symbols;
  return wifiKeyboardShifted ? WIFI_KB_LAYERS.upper : WIFI_KB_LAYERS.lower;
}

function renderWifiKeyboardKeys() {
  const container = document.getElementById("wifiKeyboardKeys");
  if (!container) return;
  container.innerHTML = "";
  for (const row of currentWifiKeyboardLayer()) {
    const rowEl = document.createElement("div");
    rowEl.className = `wifi-keyboard__row${row.rowClass ? ` ${row.rowClass}` : ""}`;
    for (const key of row.keys) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = key;
      button.setAttribute("data-wifi-kb-char", key);
      rowEl.appendChild(button);
    }
    container.appendChild(rowEl);
  }
  const shiftButton = document.querySelector('[data-wifi-kb-action="shift"]');
  if (shiftButton) {
    shiftButton.classList.toggle("is-active", wifiKeyboardShifted || wifiKeyboardSymbols);
    shiftButton.textContent = wifiKeyboardSymbols ? "ABC" : "Shift";
  }
}

function setWifiKeyboardTarget(targetId) {
  if (targetId !== "wifiSsid" && targetId !== "wifiPassword") return;
  wifiKeyboardTargetId = targetId;
  updateWifiKeyboardTargetLabel();
  wifiKeyboardTargetInput()?.focus();
}

function openWifiKeyboard(targetId) {
  const panel = document.getElementById("wifiKeyboard");
  if (!panel) {
    setOutput("Wi‑Fi keyboard is missing from this page. Use Reload Admin to refresh.");
    return;
  }
  if (targetId === "wifiSsid" || targetId === "wifiPassword") {
    wifiKeyboardTargetId = targetId;
  } else if (document.activeElement?.id === "wifiPassword") {
    wifiKeyboardTargetId = "wifiPassword";
  } else if (document.activeElement?.id === "wifiSsid") {
    wifiKeyboardTargetId = "wifiSsid";
  }
  panel.hidden = false;
  wifiKeyboardShifted = false;
  wifiKeyboardSymbols = false;
  updateWifiKeyboardTargetLabel();
  renderWifiKeyboardKeys();
  wifiKeyboardTargetInput()?.focus();
  // Bring Connect + keyboard into view (below nearby/saved lists).
  panel.scrollIntoView({ block: "nearest", behavior: "smooth" });
  const targetName = wifiKeyboardTargetId === "wifiPassword" ? "Password" : "SSID";
  setOutput(`On-screen keyboard open — typing into ${targetName}. Use Shift for uppercase/symbols.`);
}

function closeWifiKeyboard() {
  const panel = document.getElementById("wifiKeyboard");
  if (panel) panel.hidden = true;
  document.getElementById("wifiConnectForm")
    ?.querySelector('button[type="submit"]')
    ?.focus();
}

function insertWifiKeyboardChar(char) {
  const input = wifiKeyboardTargetInput();
  if (!input) return;
  const maxLength = Number(input.maxLength > 0 ? input.maxLength : 128);
  if (input.value.length >= maxLength) return;
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? input.value.length;
  input.value = `${input.value.slice(0, start)}${char}${input.value.slice(end)}`;
  const cursor = start + char.length;
  input.setSelectionRange(cursor, cursor);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  if (wifiKeyboardShifted && !wifiKeyboardSymbols) {
    wifiKeyboardShifted = false;
    renderWifiKeyboardKeys();
  }
}

function deleteWifiKeyboardChar() {
  const input = wifiKeyboardTargetInput();
  if (!input) return;
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? input.value.length;
  if (start !== end) {
    input.value = `${input.value.slice(0, start)}${input.value.slice(end)}`;
    input.setSelectionRange(start, start);
  } else if (start > 0) {
    input.value = `${input.value.slice(0, start - 1)}${input.value.slice(end)}`;
    input.setSelectionRange(start - 1, start - 1);
  }
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function clearWifiKeyboardTarget() {
  const input = wifiKeyboardTargetInput();
  if (!input) return;
  input.value = "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function toggleWifiKeyboardShift() {
  if (wifiKeyboardSymbols) {
    wifiKeyboardSymbols = false;
    wifiKeyboardShifted = false;
  } else if (wifiKeyboardShifted) {
    wifiKeyboardSymbols = true;
    wifiKeyboardShifted = false;
  } else {
    wifiKeyboardShifted = true;
  }
  renderWifiKeyboardKeys();
}

function handleWifiKeyboardClick(event) {
  const charBtn = event.target.closest("[data-wifi-kb-char]");
  if (charBtn) {
    insertWifiKeyboardChar(charBtn.getAttribute("data-wifi-kb-char") || "");
    return;
  }
  const targetBtn = event.target.closest("[data-wifi-kb-target]");
  if (targetBtn) {
    setWifiKeyboardTarget(targetBtn.getAttribute("data-wifi-kb-target") || "wifiSsid");
    return;
  }
  const actionBtn = event.target.closest("[data-wifi-kb-action]");
  if (!actionBtn) return;
  const action = actionBtn.getAttribute("data-wifi-kb-action");
  if (action === "shift") toggleWifiKeyboardShift();
  else if (action === "space") insertWifiKeyboardChar(" ");
  else if (action === "back") deleteWifiKeyboardChar();
  else if (action === "clear") clearWifiKeyboardTarget();
  else if (action === "done") closeWifiKeyboard();
}

function renderWifiStatus(status) {
  const el = document.getElementById("wifiStatusText");
  if (!el) return;
  if (!status) {
    el.textContent = "Wi‑Fi status unavailable on this display.";
    return;
  }
  const lines = [];
  if (status.on_hotspot) {
    lines.push(`On fallback hotspot: ${status.ssid || status.connection || "PAB-Hotspot"}`);
  } else if (status.ssid || status.connection) {
    lines.push(`Connected: ${status.ssid || status.connection}`);
  } else {
    lines.push("Not connected");
  }
  if (status.ipv4) lines.push(`IP: ${status.ipv4}`);
  if (status.iface) lines.push(`Interface: ${status.iface}`);
  if (status.state) lines.push(`State: ${status.state}`);
  el.textContent = lines.join("\n");
}

function renderWifiSavedList(networks) {
  const list = document.getElementById("wifiSavedList");
  if (!list) return;
  list.innerHTML = "";
  if (!networks.length) {
    list.innerHTML = "<p class=\"branding__hint\">No saved client networks yet.</p>";
    return;
  }
  for (const network of networks) {
    const item = document.createElement("div");
    item.className = "admin__item wifi-item";
    item.innerHTML = `
      <div class="admin__item-main">
        <strong>${escapeHtml(network.ssid || network.name)}</strong>
        <div class="wifi-item__meta">
          <span>Profile: ${escapeHtml(network.name)}</span>
          ${network.security ? `<span class="wifi-badge">${escapeHtml(network.security)}</span>` : ""}
        </div>
        <div class="wifi-item__actions">
          <button type="button" data-wifi-connect-saved="${escapeAttr(network.name)}">Connect</button>
          <button type="button" data-wifi-forget="${escapeAttr(network.name)}">Forget</button>
        </div>
      </div>
    `;
    list.appendChild(item);
  }
}

function renderWifiScanList(networks) {
  const list = document.getElementById("wifiScanList");
  if (!list) return;
  list.innerHTML = "";
  if (!networks.length) {
    list.innerHTML = "<p class=\"branding__hint\">No networks found. Try Scan Nearby again.</p>";
    return;
  }
  for (const network of networks) {
    const item = document.createElement("div");
    item.className = "admin__item wifi-item";
    const lock = network.secured ? "🔒" : "Open";
    item.innerHTML = `
      <div class="admin__item-main">
        <strong>${escapeHtml(network.ssid)}</strong>
        <div class="wifi-item__meta">
          <span class="wifi-badge">${network.signal}%</span>
          <span class="wifi-badge">${lock}</span>
          ${network.in_use ? "<span class=\"wifi-badge\">In use</span>" : ""}
          ${network.security ? `<span>${escapeHtml(network.security)}</span>` : ""}
        </div>
        <div class="wifi-item__actions">
          <button class="button--primary" type="button" data-wifi-pick="${escapeAttr(network.ssid)}" data-wifi-secured="${network.secured ? "1" : "0"}">
            Use this network
          </button>
        </div>
      </div>
    `;
    list.appendChild(item);
  }
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

async function loadWifiStatus() {
  try {
    const status = await api("/api/admin/wifi/status");
    renderWifiStatus(status);
  } catch (error) {
    renderWifiStatus(null);
    throw error;
  }
}

async function loadWifiSaved() {
  const payload = await api("/api/admin/wifi/saved");
  renderWifiSavedList(payload.networks || []);
}

async function loadWifiPanel() {
  try {
    await Promise.all([loadWifiStatus(), loadWifiSaved()]);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const statusEl = document.getElementById("wifiStatusText");
    if (statusEl) {
      statusEl.textContent = message.includes("local")
        ? "Wi‑Fi controls are only available on the Pi touchscreen."
        : message;
    }
    const saved = document.getElementById("wifiSavedList");
    if (saved) {
      saved.innerHTML = `<p class="branding__hint">${escapeHtml(message)}</p>`;
    }
  }
}

async function scanWifiNetworks() {
  const button = document.getElementById("scanWifi");
  setOutput("Scanning nearby Wi‑Fi (hotspot may pause briefly)…");
  if (button) button.disabled = true;
  try {
    const payload = await api("/api/admin/wifi/scan", { method: "POST" });
    renderWifiScanList(payload.networks || []);
    await loadWifiStatus();
    setOutput(`Found ${(payload.networks || []).length} nearby network(s).`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  } finally {
    if (button) button.disabled = false;
  }
}

async function connectWifi(event) {
  event.preventDefault();
  const ssid = document.getElementById("wifiSsid")?.value?.trim() || "";
  const password = document.getElementById("wifiPassword")?.value || "";
  if (!ssid) {
    setOutput("Enter an SSID first.");
    return;
  }
  setOutput(`Connecting to ${ssid}…`);
  try {
    const result = await api("/api/admin/wifi/connect", {
      method: "POST",
      body: JSON.stringify({
        ssid,
        password: password || null,
      }),
    });
    setOutput(
      `Connected to ${result.ssid || ssid}` +
        (result.ipv4 ? ` (${result.ipv4})` : "") +
        ".",
    );
    document.getElementById("wifiPassword").value = "";
    await loadWifiPanel();
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
    await loadWifiStatus();
  }
}

async function connectSavedNetwork(name) {
  setOutput(`Connecting to saved network ${name}…`);
  try {
    const result = await api("/api/admin/wifi/connect-saved", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    setOutput(
      `Connected to ${result.ssid || name}` +
        (result.ipv4 ? ` (${result.ipv4})` : "") +
        ".",
    );
    await loadWifiPanel();
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
    await loadWifiStatus();
  }
}

async function forgetSavedNetwork(name) {
  if (!window.confirm(`Forget saved network “${name}”?`)) return;
  setOutput(`Forgetting ${name}…`);
  try {
    await api(`/api/admin/wifi/saved/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
    setOutput(`Forgot ${name}.`);
    await loadWifiSaved();
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
}

function readTouchConfigPayload() {
  return {
    tap_slop: Number(document.getElementById("touchTapSlop")?.value),
    drag_start: Number(document.getElementById("touchDragStart")?.value),
    multi_tap_seconds: Number(document.getElementById("touchMultiTapSeconds")?.value),
    sensitivity: Number(document.getElementById("touchSensitivity")?.value),
    gamepad_enabled: Boolean(document.getElementById("gamepadEnabled")?.checked),
    gamepad_sensitivity: Number(document.getElementById("gamepadSensitivity")?.value),
    gamepad_deadzone: Number(document.getElementById("gamepadDeadzone")?.value),
    gamepad_edge_margin: Number(document.getElementById("gamepadEdgeMargin")?.value),
    gamepad_scroll_sensitivity: Number(document.getElementById("gamepadScrollSensitivity")?.value),
  };
}

function renderTouchConfig(config) {
  const modeInfo = document.getElementById("touchModeInfo");
  const tapSlop = document.getElementById("touchTapSlop");
  const dragStart = document.getElementById("touchDragStart");
  const multiTapSeconds = document.getElementById("touchMultiTapSeconds");
  const sensitivity = document.getElementById("touchSensitivity");
  const gamepadStatus = document.getElementById("gamepadStatus");
  const gamepadEnabled = document.getElementById("gamepadEnabled");
  const gamepadSensitivity = document.getElementById("gamepadSensitivity");
  const gamepadDeadzone = document.getElementById("gamepadDeadzone");
  const gamepadEdgeMargin = document.getElementById("gamepadEdgeMargin");
  const gamepadScrollSensitivity = document.getElementById("gamepadScrollSensitivity");
  if (modeInfo) {
    modeInfo.textContent = `Mode: ${config.touch_map} · LCD: ${config.touch_lcd}`;
  }
  if (tapSlop) tapSlop.value = String(config.tap_slop);
  if (dragStart) dragStart.value = String(config.drag_start);
  if (multiTapSeconds) multiTapSeconds.value = String(config.multi_tap_seconds);
  if (sensitivity) sensitivity.value = String(config.sensitivity);
  if (gamepadEnabled) gamepadEnabled.checked = Boolean(config.gamepad_enabled);
  if (gamepadSensitivity) gamepadSensitivity.value = String(config.gamepad_sensitivity);
  const gamepadSensitivityRange = document.getElementById("gamepadSensitivityRange");
  if (gamepadSensitivityRange) {
    gamepadSensitivityRange.value = String(config.gamepad_sensitivity);
  }
  if (gamepadDeadzone) gamepadDeadzone.value = String(config.gamepad_deadzone);
  if (gamepadEdgeMargin) gamepadEdgeMargin.value = String(config.gamepad_edge_margin);
  if (gamepadScrollSensitivity) {
    gamepadScrollSensitivity.value = String(config.gamepad_scroll_sensitivity);
  }
  if (gamepadStatus) {
    gamepadStatus.textContent = config.gamepad_device
      ? `Gamepad: connected (${config.gamepad_device})`
      : "Gamepad: not detected";
  }
}

async function loadTouchConfig() {
  const config = await api("/api/admin/touch");
  renderTouchConfig(config);
}

async function saveTouchConfig(event) {
  event.preventDefault();
  try {
    const config = await api("/api/admin/touch", {
      method: "PUT",
      body: JSON.stringify(readTouchConfigPayload()),
    });
    renderTouchConfig(config);
    setOutput("Touch settings saved. HDMI input helpers restarted.");
  } catch (error) {
    setOutput(error.message);
  }
}

async function saveGamepadConfig(event) {
  event.preventDefault();
  try {
    const config = await api("/api/admin/touch", {
      method: "PUT",
      body: JSON.stringify(readTouchConfigPayload()),
    });
    renderTouchConfig(config);
    setOutput("Gamepad settings saved. HDMI cursor restarted with new speed.");
  } catch (error) {
    setOutput(error.message);
  }
}

function renderBranding(branding) {
  const titleInput = document.getElementById("brandingTitle");
  const preview = document.getElementById("logoPreview");
  const status = document.getElementById("logoStatus");
  const fontScale = document.getElementById("boardFontScale");
  const fontLabel = document.getElementById("boardFontScaleLabel");
  if (titleInput) titleInput.value = branding.display_title || "";
  if (fontScale && Number.isFinite(Number(branding.board_font_scale))) {
    fontScale.value = String(branding.board_font_scale);
    if (fontLabel) fontLabel.textContent = `${branding.board_font_scale}%`;
  }
  if (preview && status) {
    if (branding.logo_url) {
      preview.src = branding.logo_url;
      preview.hidden = false;
      status.textContent = "Logo appears in the top-left corner of the kiosk.";
    } else {
      preview.hidden = true;
      preview.removeAttribute("src");
      status.textContent = "No logo uploaded.";
    }
  }
}

function syncBoardFontLabel() {
  const fontScale = document.getElementById("boardFontScale");
  const fontLabel = document.getElementById("boardFontScaleLabel");
  if (fontScale && fontLabel) {
    fontLabel.textContent = `${fontScale.value}%`;
  }
}

async function saveBoardFont(event) {
  event.preventDefault();
  const fontScale = document.getElementById("boardFontScale");
  if (!fontScale) return;
  try {
    const branding = await api("/api/admin/branding/board-font", {
      method: "PUT",
      body: JSON.stringify({ board_font_scale: Number(fontScale.value) }),
    });
    renderBranding(branding);
    setOutput(`Board font size saved (${branding.board_font_scale}%).`);
  } catch (error) {
    setOutput(error.message);
  }
}

function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function clampSystemClockDay() {
  const year = Number(document.getElementById("sysClockYear")?.value || 2026);
  const month = Number(document.getElementById("sysClockMonth")?.value || 1);
  const dayInput = document.getElementById("sysClockDay");
  if (!dayInput) return;
  const maxDay = daysInMonth(year, month);
  dayInput.max = String(maxDay);
  const day = Number(dayInput.value || 1);
  if (day > maxDay) dayInput.value = String(maxDay);
}

function fillSystemClockFields(localTime) {
  // Expect YYYY-MM-DDTHH:MM:SS
  const match = String(localTime || "").match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/
  );
  if (!match) return;
  const year = document.getElementById("sysClockYear");
  const month = document.getElementById("sysClockMonth");
  const day = document.getElementById("sysClockDay");
  const hour = document.getElementById("sysClockHour");
  const minute = document.getElementById("sysClockMinute");
  if (year) year.value = String(Number(match[1]));
  if (month) month.value = String(Number(match[2]));
  if (day) day.value = String(Number(match[3]));
  if (hour) hour.value = String(Number(match[4]));
  if (minute) minute.value = String(Number(match[5]));
  clampSystemClockDay();
}

function renderSystemClockStatus(clock) {
  const status = document.getElementById("systemClockStatus");
  if (!status) return;
  const ntp = clock.ntp ? "NTP on" : "NTP off";
  const persist = clock.persists_offline
    ? "survives offline reboot"
    : "may reset on reboot (fake-hwclock missing)";
  const sim = clock.simulated_kiosk ? " · Test Lab sim active" : "";
  status.textContent = `Pi clock: ${clock.local_time} (${clock.timezone}) · ${ntp} · ${persist}${sim}`;
}

async function loadSystemClock({ fillFields = true } = {}) {
  const clock = await api("/api/admin/system-clock");
  renderSystemClockStatus(clock);
  if (fillFields) fillSystemClockFields(clock.local_time);
  return clock;
}

async function saveSystemClock() {
  clampSystemClockDay();
  const payload = {
    year: Number(document.getElementById("sysClockYear")?.value),
    month: Number(document.getElementById("sysClockMonth")?.value),
    day: Number(document.getElementById("sysClockDay")?.value),
    hour: Number(document.getElementById("sysClockHour")?.value),
    minute: Number(document.getElementById("sysClockMinute")?.value),
    second: 0,
  };
  try {
    setOutput("Setting Pi system time…");
    const clock = await api("/api/admin/system-clock", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    renderSystemClockStatus(clock);
    fillSystemClockFields(clock.local_time);
    setOutput(`Pi system time set to ${clock.local_time} (${clock.timezone}).`);
  } catch (error) {
    setOutput(error.message);
  }
}

async function loadBranding() {
  const branding = await api("/api/admin/branding");
  renderBranding(branding);
}

async function saveBrandingTitle(event) {
  event.preventDefault();
  const title = document.getElementById("brandingTitle")?.value?.trim();
  if (!title) return;
  try {
    const branding = await api("/api/admin/branding", {
      method: "PUT",
      body: JSON.stringify({ display_title: title }),
    });
    renderBranding(branding);
    setOutput("Display title saved.");
  } catch (error) {
    setOutput(error.message);
  }
}

async function uploadLogoFile() {
  const input = document.getElementById("logoUpload");
  const file = input?.files?.[0];
  if (!file) {
    setOutput("Choose a PNG file first.");
    return;
  }
  if (file.type !== "image/png") {
    setOutput("Logo must be a PNG file.");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  try {
    const response = await fetch("/api/admin/branding/logo", {
      method: "POST",
      headers: {
        "X-Admin-Pin": adminPin(),
      },
      body: formData,
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Upload failed: ${response.status}`);
    }
    renderBranding(await response.json());
    if (input) input.value = "";
    setOutput("Logo uploaded.");
  } catch (error) {
    setOutput(error.message);
  }
}

async function removeLogoFile() {
  try {
    const response = await fetch("/api/admin/branding/logo", {
      method: "DELETE",
      headers: {
        "X-Admin-Pin": adminPin(),
      },
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Remove failed: ${response.status}`);
    }
    await loadBranding();
    setOutput("Logo removed.");
  } catch (error) {
    setOutput(error.message);
  }
}

participantForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const participantId = document.getElementById("participantId").value;
  const payload = {
    name: document.getElementById("participantName").value,
    race: document.getElementById("participantRace")?.value || "",
    call_up: document.getElementById("participantCallUp")?.value || null,
    event_date: document.getElementById("participantDate").value,
    start_time: document.getElementById("participantTime").value,
  };
  try {
    await api(participantId ? `/api/participants/${participantId}` : "/api/participants", {
      method: participantId ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    clearParticipantForm();
    await loadParticipants();
    setOutput("Participant saved.");
  } catch (error) {
    setOutput(error.message);
  }
});

ruleForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const ruleId = document.getElementById("ruleId").value;
  const repeat = document.getElementById("ruleRepeat").value;
  const payload = {
    offset_minutes: Number(document.getElementById("ruleOffset").value),
    message_template: document.getElementById("ruleMessage").value,
    repeat_every_minutes: repeat ? Number(repeat) : null,
    enabled: document.getElementById("ruleEnabled").checked,
    sort_order: 0,
    ...readRuleLedSettings(),
    ...readRuleBuzzerSettings(),
    ...readRuleSoundSettings(),
  };
  try {
    await api(ruleId ? `/api/reminder-rules/${ruleId}` : "/api/reminder-rules", {
      method: ruleId ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    clearRuleForm();
    await loadRules();
    setOutput("Reminder rule saved.");
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("brandingForm")?.addEventListener("submit", saveBrandingTitle);
document.getElementById("boardFontForm")?.addEventListener("submit", saveBoardFont);
document.getElementById("boardFontScale")?.addEventListener("input", syncBoardFontLabel);
document.getElementById("refreshSystemClock")?.addEventListener("click", async () => {
  try {
    await loadSystemClock({ fillFields: true });
    setOutput("Loaded current Pi system time.");
  } catch (error) {
    setOutput(error.message);
  }
});
document.getElementById("saveSystemClock")?.addEventListener("click", saveSystemClock);
["sysClockYear", "sysClockMonth"].forEach((id) => {
  document.getElementById(id)?.addEventListener("input", clampSystemClockDay);
});
document.getElementById("touchForm")?.addEventListener("submit", saveTouchConfig);
document.getElementById("gamepadForm")?.addEventListener("submit", saveGamepadConfig);

function initTouchSteppers() {
  document.querySelectorAll("[data-touch-stepper]").forEach((wrapper) => {
    const input = wrapper.querySelector(".touch-stepper__value");
    if (!input) return;

    wrapper.querySelectorAll("[data-touch-stepper-delta]").forEach((button) => {
      button.addEventListener("click", () => {
        const delta = Number(button.getAttribute("data-touch-stepper-delta") || "0");
        const step = Number(input.step || "1") || 1;
        const min = input.min === "" ? Number.NEGATIVE_INFINITY : Number(input.min);
        const max = input.max === "" ? Number.POSITIVE_INFINITY : Number(input.max);
        const decimals = (String(step).split(".")[1] || "").length;
        const next = Math.min(max, Math.max(min, Number(input.value || "0") + delta * step));
        input.value = decimals ? next.toFixed(decimals) : String(next);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
    });
  });
}

const gamepadSensitivity = document.getElementById("gamepadSensitivity");
const gamepadSensitivityRange = document.getElementById("gamepadSensitivityRange");
if (gamepadSensitivity && gamepadSensitivityRange) {
  gamepadSensitivityRange.addEventListener("input", () => {
    gamepadSensitivity.value = gamepadSensitivityRange.value;
  });
  gamepadSensitivity.addEventListener("input", () => {
    gamepadSensitivityRange.value = gamepadSensitivity.value;
  });
}

initTouchSteppers();
configureMusicBreaks();
document.getElementById("uploadLogo")?.addEventListener("click", uploadLogoFile);
document.getElementById("uploadSound")?.addEventListener("click", uploadSoundFile);
document.getElementById("removeLogo")?.addEventListener("click", removeLogoFile);
document.getElementById("clearParticipant")?.addEventListener("click", clearParticipantForm);
document.getElementById("clearRule")?.addEventListener("click", clearRuleForm);
document.querySelectorAll(".color-preset").forEach((button) => {
  button.addEventListener("click", () => {
    const color = button.dataset.color;
    const colorInput = document.getElementById("ruleLedColor");
    if (color && colorInput) colorInput.value = color;
  });
});
document.getElementById("testRuleBuzzer")?.addEventListener("click", async () => {
  let buzzerSettings;
  try {
    buzzerSettings = readRuleBuzzerSettings();
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
    return;
  }
  setOutput("Testing buzzer...");
  try {
    await api("/api/admin/buzzer/test", {
      method: "POST",
      body: JSON.stringify(buzzerSettings),
    });
    setOutput(
      `Buzzer test started (${buzzerSettings.buzzer_count} beeps @ ${buzzerSettings.buzzer_pitch_hz}Hz)`,
    );
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("testRuleSound")?.addEventListener("click", async () => {
  const soundSettings = readRuleSoundSettings();
  if (!soundSettings.sound_id) {
    setOutput("Choose a sound file first (upload in Sounds tab).");
    return;
  }
  setOutput("Testing HDMI sound...");
  try {
    await api(`/api/admin/sounds/${soundSettings.sound_id}/test`, {
      method: "POST",
      body: JSON.stringify({ volume: soundSettings.sound_volume }),
    });
    setOutput(`HDMI sound test started (volume ${soundSettings.sound_volume}).`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("testRuleLed")?.addEventListener("click", async () => {
  const ledSettings = readRuleLedSettings();
  const totalSeconds =
    ledSettings.led_flash_duration_seconds + (ledSettings.led_chase_duration_seconds || 0);
  setOutput(`Connecting to LED strip… (test will run ~${totalSeconds}s)`);
  try {
    const result = await api("/api/admin/led/test", {
      method: "POST",
      body: JSON.stringify(ledSettings),
    });
    setOutput(
      `✅ LED test complete (${ledSettings.led_flash_duration_seconds}s flash, ${ledSettings.led_flash_interval_ms}ms interval` +
        (ledSettings.led_chase_duration_seconds > 0
          ? `, then ${ledSettings.led_chase_duration_seconds}s chase`
          : "") +
        `)${result.address ? " — device " + result.address : ""}.`,
    );
  } catch (error) {
    setOutput("❌ " + (error instanceof Error ? error.message : String(error)));
  }
});

document.getElementById("testRuleMatrix")?.addEventListener("click", async () => {
  const ledSettings = readRuleLedSettings();
  const message =
    document.getElementById("ruleMessage")?.value?.trim() || "Matrix test";
  const totalSeconds =
    ledSettings.led_flash_duration_seconds + (ledSettings.led_chase_duration_seconds || 0);
  setOutput(`Testing matrix scroll (“${message}”, ${ledSettings.matrix_effect}, ~${totalSeconds}s)…`);
  try {
    await api("/api/admin/matrix/test", {
      method: "POST",
      body: JSON.stringify({ ...ledSettings, message }),
    });
    setOutput(
      `Matrix test started — ${ledSettings.matrix_effect} scroll “${message}” for ~${totalSeconds}s`,
    );
  } catch (error) {
    setOutput("❌ " + (error instanceof Error ? error.message : String(error)));
  }
});

document.getElementById("participantDate")?.addEventListener("change", loadParticipants);
document.querySelectorAll("[data-pin-digit]").forEach((button) => {
  const digit = button.dataset.pinDigit || "";
  bindPinActivation(button, `digit-${digit}`, () => appendPinDigit(digit));
});
bindPinActivation(
  document.querySelector("[data-pin-delete]"),
  "delete",
  deletePinDigit,
);
bindPinActivation(
  document.querySelector("[data-pin-clear]"),
  "clear",
  clearPinDigits,
);
if (savePin) {
  bindPinActivation(savePin, "unlock", unlock);
}
document.querySelectorAll("[data-open-keyboard]").forEach((button) => {
  button.addEventListener("click", openKeyboard);
});
pinInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") unlock();
});

document.getElementById("runScenarioTest")?.addEventListener("click", async () => {
  if (!currentScenario) {
    setOutput("No scenario selected.");
    return;
  }
  const runBtn = document.getElementById("runScenarioTest");
  runBtn.textContent = "Running...";
  runBtn.disabled = true;
  try {
    const result = await api(`/api/admin/test-scenarios/${currentScenario.id}/run`, {
      method: "POST",
    });
    await Promise.all([loadParticipants(), loadRaceResults(), loadKioskClockStatus()]);
    setOutput(
      `Seeded ${result.participants_seeded} riders. ` +
        `Sat matched ${result.saturday.matched}/${result.saturday.matched + result.saturday.unmatched + result.saturday.ambiguous}, ` +
        `Sun matched ${result.sunday.matched}/${result.sunday.matched + result.sunday.unmatched + result.sunday.ambiguous}. ` +
        `Kiosk sim: ${result.simulated_now}`,
    );
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  } finally {
    updateRunButtonLabel();
    runBtn.disabled = false;
  }
});

document.getElementById("applyKioskClock")?.addEventListener("click", async () => {
  const value = document.getElementById("kioskSimDateTime")?.value;
  if (!value) {
    setOutput("Choose a simulated date and time first.");
    return;
  }
  try {
    const clock = await api("/api/admin/kiosk-clock", {
      method: "PUT",
      headers: { "X-Admin-Pin": adminPin() },
      body: JSON.stringify({ simulated_now: value, running: true }),
    });
    await loadKioskClockStatus();
    setOutput(`Kiosk clock set to ${clock.kiosk_now} (running).`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("pauseKioskClock")?.addEventListener("click", async () => {
  const value = document.getElementById("kioskSimDateTime")?.value;
  if (!value) {
    setOutput("Choose a simulated date and time first.");
    return;
  }
  try {
    const clock = await api("/api/admin/kiosk-clock", {
      method: "PUT",
      headers: { "X-Admin-Pin": adminPin() },
      body: JSON.stringify({ simulated_now: value, running: false }),
    });
    await loadKioskClockStatus();
    setOutput(`Kiosk clock paused at ${clock.kiosk_now}.`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("resetKioskClock")?.addEventListener("click", async () => {
  try {
    await api("/api/admin/kiosk-clock", {
      method: "DELETE",
      headers: { "X-Admin-Pin": adminPin() },
    });
    await loadKioskClockStatus();
    setOutput("Kiosk clock reset to real time.");
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("openTestKiosk")?.addEventListener("click", () => {
  window.location.href = "/?testlab=1";
});

// --- Scenario roster management ---

async function loadScenarioList() {
  const select = document.getElementById("scenarioSelect");
  if (!select) return;
  try {
    const scenarios = await api("/api/admin/test-scenarios", {
      headers: { "X-Admin-Pin": adminPin() },
    });
    select.innerHTML = "";
    for (const s of scenarios) {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.label;
      select.appendChild(opt);
    }
    if (scenarios.length > 0) {
      await loadScenario(scenarios[0].id);
    }
  } catch {
    // scenarios not available
  }
}

function updateRunButtonLabel() {
  const btn = document.getElementById("runScenarioTest");
  if (btn && currentScenario) {
    btn.textContent = `Run ${currentScenario.label}`;
  }
}

async function loadScenario(scenarioId) {
  try {
    const scenario = await api(`/api/admin/test-scenarios/${scenarioId}`, {
      headers: { "X-Admin-Pin": adminPin() },
    });
    currentScenario = scenario;
    DEFAULT_SIM_TIME = scenario.default_simulated_now.slice(0, 16);
    document.getElementById("scenarioLabel").value = scenario.label;
    document.getElementById("scenarioIyrId").value = scenario.iyr_series_id || "";
    document.getElementById("scenarioSaturday").value = scenario.saturday;
    document.getElementById("scenarioSunday").value = scenario.sunday;
    document.getElementById("scenarioFirstStart").value = scenario.first_start_time;
    document.getElementById("scenarioStagger").value = scenario.stagger_minutes;
    renderRoster(scenario.roster);
    updateRunButtonLabel();
    updateScenarioSummary(scenario);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
}

function updateScenarioSummary(scenario) {
  const datesEl = document.getElementById("scenarioSummaryDates");
  const ridersEl = document.getElementById("scenarioSummaryRiders");
  if (datesEl) {
    datesEl.textContent = `📅 ${scenario.saturday} / ${scenario.sunday}`;
  }
  if (ridersEl) {
    const count = scenario.roster ? scenario.roster.length : 0;
    ridersEl.textContent = `👤 ${count} rider${count !== 1 ? "s" : ""}`;
  }
}

function renderRoster(roster) {
  const tbody = document.getElementById("rosterBody");
  if (!tbody) return;
  tbody.innerHTML = "";
  for (let i = 0; i < roster.length; i++) {
    const rider = roster[i];
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td><input type="text" value="${rider.name}" data-field="name" data-index="${i}" class="roster-input" /></td>` +
      `<td><select data-field="day" data-index="${i}">` +
      `<option value="saturday"${rider.day === "saturday" ? " selected" : ""}>Saturday</option>` +
      `<option value="sunday"${rider.day === "sunday" ? " selected" : ""}>Sunday</option>` +
      `</select></td>` +
      `<td><button type="button" class="roster-remove" data-index="${i}">✕</button></td>`;
    tbody.appendChild(tr);
  }
}

function collectRoster() {
  const tbody = document.getElementById("rosterBody");
  if (!tbody) return [];
  const roster = [];
  const rows = tbody.querySelectorAll("tr");
  for (const row of rows) {
    const nameInput = row.querySelector("[data-field='name']");
    const daySelect = row.querySelector("[data-field='day']");
    if (nameInput && daySelect && nameInput.value.trim()) {
      roster.push({ name: nameInput.value.trim(), day: daySelect.value });
    }
  }
  return roster;
}

document.getElementById("scenarioSelect")?.addEventListener("change", (e) => {
  loadScenario(e.target.value);
});

document.getElementById("rosterBody")?.addEventListener("click", (e) => {
  if (e.target.classList.contains("roster-remove")) {
    e.target.closest("tr").remove();
  }
});

document.getElementById("addRider")?.addEventListener("click", () => {
  const tbody = document.getElementById("rosterBody");
  if (!tbody) return;
  const index = tbody.querySelectorAll("tr").length;
  const tr = document.createElement("tr");
  tr.innerHTML =
    `<td><input type="text" value="" data-field="name" data-index="${index}" class="roster-input" placeholder="Rider name" /></td>` +
    `<td><select data-field="day" data-index="${index}">` +
    `<option value="saturday">Saturday</option>` +
    `<option value="sunday">Sunday</option>` +
    `</select></td>` +
    `<td><button type="button" class="roster-remove" data-index="${index}">✕</button></td>`;
  tbody.appendChild(tr);
  tr.querySelector("input")?.focus();
});

document.getElementById("saveScenario")?.addEventListener("click", async () => {
  if (!currentScenario) {
    setOutput("No scenario loaded.");
    return;
  }
  const label = document.getElementById("scenarioLabel")?.value?.trim();
  const iyrId = document.getElementById("scenarioIyrId")?.value?.trim() || "";
  const saturday = document.getElementById("scenarioSaturday")?.value;
  const sunday = document.getElementById("scenarioSunday")?.value;
  const firstStart = document.getElementById("scenarioFirstStart")?.value;
  const stagger = parseInt(document.getElementById("scenarioStagger")?.value || "15", 10);
  if (!label || !saturday || !sunday || !firstStart) {
    setOutput("Fill in label and all date/time fields.");
    return;
  }
  const roster = collectRoster();
  if (roster.length === 0) {
    setOutput("Roster is empty.");
    return;
  }
  const updatedScenario = {
    ...currentScenario,
    label,
    iyr_series_id: iyrId,
    saturday,
    sunday,
    first_start_time: firstStart,
    stagger_minutes: stagger,
    default_simulated_now: `${saturday}T${firstStart}:00`,
    roster,
  };
  setOutput("Saving scenario...");
  try {
    await api(`/api/admin/test-scenarios/${currentScenario.id}`, {
      method: "PUT",
      body: JSON.stringify(updatedScenario),
    });
    currentScenario = updatedScenario;
    DEFAULT_SIM_TIME = updatedScenario.default_simulated_now.slice(0, 16);
    updateRunButtonLabel();
    updateScenarioSummary(updatedScenario);
    // Update the dropdown label
    const opt = document.querySelector(`#scenarioSelect option[value="${currentScenario.id}"]`);
    if (opt) opt.textContent = label;
    setOutput(`Scenario saved: ${roster.length} riders.`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("clearTestData")?.addEventListener("click", async () => {
  if (!currentScenario) {
    setOutput("No scenario loaded.");
    return;
  }
  if (!confirm(`Clear all test participants and results for ${currentScenario.label}?`)) {
    return;
  }
  setOutput("Clearing test data...");
  try {
    const result = await api(`/api/admin/test-scenarios/${currentScenario.id}/data`, {
      method: "DELETE",
      headers: { "X-Admin-Pin": adminPin() },
    });
    await api("/api/admin/kiosk-clock", {
      method: "DELETE",
      headers: { "X-Admin-Pin": adminPin() },
    });
    await Promise.all([loadParticipants(), loadRaceResults(), loadKioskClockStatus()]);
    setOutput(
      `Cleared ${result.participants_deleted} participants, ${result.results_deleted} results. Clock reset.`,
    );
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("newScenario")?.addEventListener("click", async () => {
  const label = prompt("Scenario label (e.g. MCA 2025 Austin):");
  if (!label) return;
  const slug = label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  if (!slug) {
    setOutput("Could not generate a valid id from that label.");
    return;
  }
  const today = new Date();
  const satDate = localDateParam(today);
  const sunDate = localDateParam(new Date(today.getTime() + 86400000));
  const scenario = {
    id: slug,
    label,
    iyr_series_id: "",
    saturday: satDate,
    sunday: sunDate,
    first_start_time: "08:00",
    stagger_minutes: 2,
    default_simulated_now: `${satDate}T10:25:00`,
    roster: [],
  };
  setOutput("Creating scenario...");
  try {
    await api("/api/admin/test-scenarios", {
      method: "POST",
      body: JSON.stringify(scenario),
    });
    await loadScenarioList();
    // select the newly created scenario
    const select = document.getElementById("scenarioSelect");
    if (select) {
      select.value = slug;
      await loadScenario(slug);
    }
    setOutput(`Created scenario "${label}".`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("deleteScenario")?.addEventListener("click", async () => {
  if (!currentScenario) {
    setOutput("No scenario loaded.");
    return;
  }
  if (!confirm(`Delete scenario "${currentScenario.label}"? This cannot be undone.`)) {
    return;
  }
  setOutput("Deleting scenario...");
  try {
    await api(`/api/admin/test-scenarios/${currentScenario.id}`, {
      method: "DELETE",
      headers: { "X-Admin-Pin": adminPin() },
    });
    await loadScenarioList();
    setOutput("Scenario deleted.");
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("syncRaceIndex")?.addEventListener("click", async () => {
  setOutput("Syncing MCA index...");
  try {
    const events = await api("/api/admin/race-results/sync-index", {
      method: "POST",
      headers: { "X-Admin-Pin": adminPin() },
    });
    setOutput(`Synced ${events.length} MCA race events.`);
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("syncRaceResults")?.addEventListener("click", async () => {
  const date = document.getElementById("raceResultsDate")?.value || todayParam;
  setOutput(`Sync Now: pulling race results for ${date}...`);
  try {
    const summary = await api(`/api/admin/race-results/sync-date?date=${date}`, {
      method: "POST",
      headers: { "X-Admin-Pin": adminPin() },
    });
    await loadRaceResults();
    await loadSyncConfig();
    setOutput(
      `Sync Now done — matched ${summary.matched}, unmatched ${summary.unmatched}, ambiguous ${summary.ambiguous}, sessions ${summary.sessions_synced}.`,
    );
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

// --- Sync config (interval + window) ---

function formatSyncClock(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso);
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function renderSyncConfigStatus(data) {
  const statusEl = document.getElementById("syncIntervalStatus");
  if (!statusEl) return;
  if (!data || data.interval_minutes <= 0) {
    statusEl.textContent = "Auto-sync disabled";
    return;
  }
  const parts = [`Auto-sync ON · every ${data.interval_minutes} min`];
  parts.push(`window ${data.window_hours}h after last start`);
  if (data.active && data.window_end) {
    parts.push(`active until ${formatSyncClock(data.window_end)}`);
  } else if (data.next_eligible) {
    parts.push(`waiting until first start ${formatSyncClock(data.next_eligible)}`);
  } else if (data.window_end) {
    parts.push(`ended ${formatSyncClock(data.window_end)}`);
  } else {
    parts.push("no starts scheduled today");
  }
  statusEl.textContent = parts.join(" · ");
}

async function loadSyncConfig() {
  const intervalInput = document.getElementById("syncIntervalMinutes");
  const windowInput = document.getElementById("syncWindowHours");
  if (!intervalInput) return;
  try {
    const data = await api("/api/admin/race-results/sync-config", {
      headers: { "X-Admin-Pin": adminPin() },
    });
    intervalInput.value = String(data.interval_minutes);
    if (windowInput) windowInput.value = String(data.window_hours);
    renderSyncConfigStatus(data);
  } catch {
    // not available
  }
}

async function loadSyncInterval() {
  return loadSyncConfig();
}

async function loadHardwareStatus() {
  const el = document.getElementById("hardwareStatus");
  if (!el) return;
  try {
    const hw = await api("/api/admin/hardware-status", {
      headers: { "X-Admin-Pin": adminPin() },
    });
    const issues = [];
    if (!hw.buzzer_enabled) issues.push("Buzzer disabled (PAB_BUZZER_ENABLED)");
    else if (!hw.buzzer_port) issues.push("Buzzer port not set (PAB_BUZZER_PORT)");
    if (!hw.led_enabled) issues.push("BLE LED disabled (PAB_LED_ENABLED)");
    else if (!hw.led_address) issues.push("BLE LED address not set (PAB_LED_ADDRESS)");
    if (!hw.matrix_enabled) issues.push("Matrix disabled (PAB_MATRIX_ENABLED)");
    else if (!hw.matrix_port) issues.push("Matrix port not set (PAB_MATRIX_PORT)");
    if (!hw.sound_enabled) issues.push("HDMI sound disabled (PAB_SOUND_ENABLED)");
    if (issues.length > 0) {
      el.textContent = "⚠ " + issues.join(" · ");
      el.hidden = false;
    } else {
      el.hidden = true;
    }
  } catch {
    // endpoint not available
  }
}

// --- LED strip config ---

async function loadMatrixStatus() {
  const statusEl = document.getElementById("matrixStatus");
  if (!statusEl) return;
  try {
    const hw = await api("/api/admin/hardware-status", {
      headers: { "X-Admin-Pin": adminPin() },
    });
    if (hw.matrix_enabled && hw.matrix_port) {
      statusEl.textContent =
        `Matrix: ✅ enabled — ${hw.matrix_port} (brightness ${hw.matrix_brightness})`;
      statusEl.style.color = "#4ade80";
    } else if (hw.matrix_port) {
      statusEl.textContent = `Matrix: ⚠ disabled — ${hw.matrix_port}`;
      statusEl.style.color = "#fbbf24";
    } else {
      statusEl.textContent = "Matrix: ❌ not configured";
      statusEl.style.color = "#f87171";
    }
  } catch {
    statusEl.textContent = "Matrix: unavailable";
    statusEl.style.color = "#94a3b8";
  }
}

async function loadLedConfig() {
  const statusEl = document.getElementById("ledStatus");
  const enabledEl = document.getElementById("ledConfigEnabled");
  const addressEl = document.getElementById("ledConfigAddress");
  const nameEl = document.getElementById("ledConfigName");
  if (!statusEl) return;
  try {
    const cfg = await api("/api/admin/led/config", {
      headers: { "X-Admin-Pin": adminPin() },
    });
    if (enabledEl) enabledEl.checked = cfg.led_enabled;
    if (addressEl) addressEl.value = cfg.led_address || "";
    if (nameEl) nameEl.value = cfg.led_name || "";
    if (cfg.led_enabled && cfg.led_address) {
      statusEl.textContent = `LED: ✅ enabled — ${cfg.led_address}`;
      statusEl.style.color = "#4ade80";
    } else if (cfg.led_address) {
      statusEl.textContent = `LED: ⚠ disabled — ${cfg.led_address}`;
      statusEl.style.color = "#fbbf24";
    } else {
      statusEl.textContent = "LED: ❌ not configured";
      statusEl.style.color = "#f87171";
    }
  } catch {
    statusEl.textContent = "LED: unavailable";
    statusEl.style.color = "#94a3b8";
  }
}

document.getElementById("saveLedConfig")?.addEventListener("click", async () => {
  const enabled = document.getElementById("ledConfigEnabled")?.checked || false;
  const address = document.getElementById("ledConfigAddress")?.value?.trim() || "";
  const name = document.getElementById("ledConfigName")?.value?.trim() || "";
  if (enabled && !address) {
    setOutput("Enter a BLE MAC address or scan for devices first.");
    return;
  }
  try {
    await api("/api/admin/led/config", {
      method: "PUT",
      body: JSON.stringify({ led_enabled: enabled, led_address: address, led_name: name }),
    });
    await loadLedConfig();
    await loadHardwareStatus();
    setOutput(enabled ? `LED strip saved: ${address}` : "LED strip disabled.");
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("scanBle")?.addEventListener("click", async () => {
  const selectEl = document.getElementById("bleScanResults");
  setOutput("Scanning for BLE devices… (10 seconds)");
  try {
    const devices = await api("/api/admin/led/scan", {
      method: "POST",
      headers: { "X-Admin-Pin": adminPin() },
    });
    if (!selectEl) return;
    selectEl.innerHTML = '<option value="">— select a device —</option>';
    for (const d of devices) {
      const opt = document.createElement("option");
      opt.value = d.address;
      opt.textContent = `${d.name} (${d.address})`;
      opt.dataset.name = d.name;
      selectEl.appendChild(opt);
    }
    selectEl.hidden = false;
    setOutput(`Found ${devices.length} BLE device(s).`);
  } catch (error) {
    setOutput("❌ " + (error instanceof Error ? error.message : String(error)));
  }
});

document.getElementById("bleScanResults")?.addEventListener("change", (e) => {
  const opt = e.target.selectedOptions[0];
  if (!opt || !opt.value) return;
  const addressEl = document.getElementById("ledConfigAddress");
  const nameEl = document.getElementById("ledConfigName");
  if (addressEl) addressEl.value = opt.value;
  if (nameEl && opt.dataset.name) nameEl.value = opt.dataset.name;
});

document.getElementById("saveSyncConfig")?.addEventListener("click", async () => {
  const intervalInput = document.getElementById("syncIntervalMinutes");
  const windowInput = document.getElementById("syncWindowHours");
  const interval = parseInt(intervalInput?.value || "5", 10);
  const windowHours = parseInt(windowInput?.value || "3", 10);
  if (Number.isNaN(interval) || interval < 0) {
    setOutput("Enter a valid interval (0 = off, or 1–1440 minutes).");
    return;
  }
  if (Number.isNaN(windowHours) || windowHours < 1 || windowHours > 24) {
    setOutput("Enter a valid window (1–24 hours after last start).");
    return;
  }
  try {
    const data = await api("/api/admin/race-results/sync-config", {
      method: "PUT",
      body: JSON.stringify({
        interval_minutes: interval,
        window_hours: windowHours,
      }),
    });
    renderSyncConfigStatus(data);
    if (intervalInput) intervalInput.value = String(data.interval_minutes);
    if (windowInput) windowInput.value = String(data.window_hours);
    setOutput(
      interval > 0
        ? `Auto-sync every ${interval} min · ${windowHours}h after last start.`
        : "Auto-sync disabled.",
    );
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});

document.getElementById("importSchedule")?.addEventListener("click", async () => {
  try {
    const raw = document.getElementById("importJson").value;
    await api("/api/import", {
      method: "POST",
      body: raw,
    });
    await loadAll();
    setOutput("Imported schedule JSON.");
  } catch (error) {
    setOutput(error.message);
  }
});

document.getElementById("importCsv")?.addEventListener("click", async () => {
  const input = document.getElementById("csvImportFile");
  const statusEl = document.getElementById("csvImportStatus");
  const file = input?.files?.[0];
  if (!file) {
    if (statusEl) statusEl.textContent = "Choose a CSV file first.";
    return;
  }
  const eventDate = document.getElementById("csvImportDate")?.value || todayParam;
  const formData = new FormData();
  formData.append("file", file);
  formData.append("event_date", eventDate);
  if (statusEl) statusEl.textContent = "Importing…";
  try {
    const response = await fetch("/api/import/csv", {
      method: "POST",
      headers: { "X-Admin-Pin": adminPin() },
      body: formData,
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Import failed (${response.status})`);
    }
    const result = await response.json();
    if (input) input.value = "";
    const msg = `Imported ${result.participant_count} participant(s) for ${result.event_date}.`;
    if (statusEl) statusEl.textContent = msg;
    const participantDate = document.getElementById("participantDate");
    if (participantDate) participantDate.value = result.event_date;
    await loadAll();
    setOutput(msg);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (statusEl) statusEl.textContent = message;
    setOutput(message);
  }
});

document.getElementById("exportSchedule")?.addEventListener("click", async () => {
  try {
    const date = document.getElementById("importDate").value || todayParam;
    const exported = await api(`/api/export?date=${date}`, {
      headers: { "X-Admin-Pin": adminPin() },
    });
    setOutput(JSON.stringify(exported, null, 2));
  } catch (error) {
    setOutput(error.message);
  }
});

restartServiceButton?.addEventListener("click", restartService);
reloadKioskDisplayButton?.addEventListener("click", reloadKioskDisplay);
reloadAdminPageButton?.addEventListener("click", hardReloadAdminPage);

document.getElementById("refreshWifiStatus")?.addEventListener("click", async () => {
  try {
    await loadWifiStatus();
    setOutput("Wi‑Fi status refreshed.");
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});
document.getElementById("scanWifi")?.addEventListener("click", scanWifiNetworks);
document.getElementById("wifiConnectForm")?.addEventListener("submit", connectWifi);
document.getElementById("openWifiKeyboard")?.addEventListener("click", () => {
  openWifiKeyboard();
});
document.getElementById("wifiKeyboard")?.addEventListener("click", handleWifiKeyboardClick);

document.getElementById("wifiSavedList")?.addEventListener("click", async (event) => {
  const connectBtn = event.target.closest("[data-wifi-connect-saved]");
  if (connectBtn) {
    await connectSavedNetwork(connectBtn.dataset.wifiConnectSaved || "");
    return;
  }
  const forgetBtn = event.target.closest("[data-wifi-forget]");
  if (forgetBtn) {
    await forgetSavedNetwork(forgetBtn.dataset.wifiForget || "");
  }
});

document.getElementById("wifiScanList")?.addEventListener("click", (event) => {
  const pickBtn = event.target.closest("[data-wifi-pick]");
  if (!pickBtn) return;
  const ssid = pickBtn.dataset.wifiPick || "";
  const secured = pickBtn.dataset.wifiSecured === "1";
  fillWifiConnectForm(ssid, secured);
  if (secured) {
    openWifiKeyboard("wifiPassword");
  } else {
    openWifiKeyboard("wifiSsid");
  }
  setOutput(`Selected ${ssid}. Enter password if needed, then Connect.`);
});

document.getElementById("participantDate").value = todayParam;
document.getElementById("importDate").value = todayParam;
document.getElementById("csvImportDate").value = todayParam;
document.getElementById("raceResultsDate").value = todayParam;

ruleList?.addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-rule]");
  if (editButton) {
    const ruleId = editButton.dataset.editRule;
    const rule = cachedRules.find((item) => String(item.id) === String(ruleId));
    if (!rule) {
      setOutput("Could not find that rule. Reloading list...");
      await loadRules();
      return;
    }
    populateRuleForm(rule);
    return;
  }

  const deleteButton = event.target.closest("[data-delete-rule]");
  if (deleteButton) {
    await api(`/api/reminder-rules/${deleteButton.dataset.deleteRule}`, {
      method: "DELETE",
    });
    await loadRules();
  }
});

registerServiceWorker();
document.querySelectorAll("[data-tab-panel]").forEach((button) => {
  button.addEventListener("click", () => {
    showPanel(button.dataset.tabPanel);
  });
});

if (adminPin()) {
  verifyPin(adminPin()).then((valid) => {
    if (valid) {
      revealAdmin();
    } else {
      sessionStorage.removeItem("pabAdminPin");
      setAdminVisible(false);
      setPinMessage("Enter admin PIN.");
    }
  });
} else {
  setAdminVisible(false);
}
