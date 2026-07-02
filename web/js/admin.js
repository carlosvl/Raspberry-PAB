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

const todayParam = new Date().toISOString().slice(0, 10);

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
    setFieldChecked("ruleBuzzerEnabled", rule.buzzer_enabled);
    setFieldValue("ruleBuzzerPitch", String(rule.buzzer_pitch_hz ?? 2500));
    setFieldValue("ruleBuzzerVolume", String(rule.buzzer_volume ?? 80));
    setFieldValue("ruleBuzzerCount", String(rule.buzzer_count ?? 3));
    setFieldValue("ruleBuzzerBeepMs", String(rule.buzzer_beep_ms ?? 200));
    setFieldValue("ruleBuzzerGapMs", String(rule.buzzer_gap_ms ?? 150));
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
  return {
    led_enabled: document.getElementById("ruleLedEnabled").checked,
    led_red: ledColor.led_red,
    led_green: ledColor.led_green,
    led_blue: ledColor.led_blue,
    led_flash_interval_ms: readRuleNumber("ruleLedInterval", 500),
    led_flash_duration_seconds: readRuleNumber("ruleLedDuration", 10),
    led_chase_duration_seconds: readRuleNumber("ruleLedChaseDuration", 10),
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

function ruleBuzzerSummary(rule) {
  if (!rule.buzzer_enabled) {
    return "";
  }
  return ` · Buzzer ${rule.buzzer_count}x @ ${rule.buzzer_pitch_hz}Hz`;
}

function ruleLedSummary(rule) {
  if (!rule.led_enabled) {
    return "";
  }
  const color = rgbToHex(rule.led_red, rule.led_green, rule.led_blue);
  return ` · LED ${color} @ ${rule.led_flash_interval_ms}ms for ${rule.led_flash_duration_seconds}s` +
    (rule.led_chase_duration_seconds > 0
      ? `, then chase ${rule.led_chase_duration_seconds}s`
      : "");
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

function scrollToPanel(targetId) {
  const panel = document.getElementById(targetId);
  if (!panel) return;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: headers(options.headers || {}),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
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
  document.getElementById("ruleBuzzerEnabled").checked = false;
  document.getElementById("ruleBuzzerPitch").value = "2500";
  document.getElementById("ruleBuzzerVolume").value = "80";
  document.getElementById("ruleBuzzerCount").value = "3";
  document.getElementById("ruleBuzzerBeepMs").value = "200";
  document.getElementById("ruleBuzzerGapMs").value = "150";
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
            <span>${escapeHtml(item.event_date)} ${escapeHtml(formatDisplayTime(item.start_time, item.event_date))}</span>
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
      (rule) => `
        <div class="admin__item">
          <div class="admin__item-main">
            <strong>${escapeHtml(rule.offset_minutes)} min: ${escapeHtml(rule.message_template)}</strong>
            <span>${rule.repeat_every_minutes ? `Repeats every ${escapeHtml(rule.repeat_every_minutes)} min` : "One time"} · ${rule.enabled ? "Enabled" : "Disabled"}${escapeHtml(ruleLedSummary(rule))}${escapeHtml(ruleBuzzerSummary(rule))}</span>
          </div>
          <button data-edit-rule="${rule.id}" type="button">Edit</button>
          <button data-delete-rule="${rule.id}" type="button">Delete</button>
        </div>
      `,
    )
    .join("");
}

async function loadAll() {
  try {
    await Promise.all([loadBranding(), loadTouchConfig(), loadParticipants(), loadRules()]);
    setOutput("Loaded.");
  } catch (error) {
    setOutput(error.message);
  }
}

function renderTouchConfig(config) {
  const modeInfo = document.getElementById("touchModeInfo");
  const tapSlop = document.getElementById("touchTapSlop");
  const dragStart = document.getElementById("touchDragStart");
  const multiTapSeconds = document.getElementById("touchMultiTapSeconds");
  const sensitivity = document.getElementById("touchSensitivity");
  if (modeInfo) {
    modeInfo.textContent = `Mode: ${config.touch_map} · LCD: ${config.touch_lcd}`;
  }
  if (tapSlop) tapSlop.value = String(config.tap_slop);
  if (dragStart) dragStart.value = String(config.drag_start);
  if (multiTapSeconds) multiTapSeconds.value = String(config.multi_tap_seconds);
  if (sensitivity) sensitivity.value = String(config.sensitivity);
}

async function loadTouchConfig() {
  const config = await api("/api/admin/touch");
  renderTouchConfig(config);
}

async function saveTouchConfig(event) {
  event.preventDefault();
  const payload = {
    tap_slop: Number(document.getElementById("touchTapSlop")?.value),
    drag_start: Number(document.getElementById("touchDragStart")?.value),
    multi_tap_seconds: Number(document.getElementById("touchMultiTapSeconds")?.value),
    sensitivity: Number(document.getElementById("touchSensitivity")?.value),
  };
  try {
    const config = await api("/api/admin/touch", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    renderTouchConfig(config);
    setOutput("Touch settings saved and applied.");
  } catch (error) {
    setOutput(error.message);
  }
}

function renderBranding(branding) {
  const titleInput = document.getElementById("brandingTitle");
  const preview = document.getElementById("logoPreview");
  const status = document.getElementById("logoStatus");
  if (titleInput) titleInput.value = branding.display_title || "";
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
document.getElementById("touchForm")?.addEventListener("submit", saveTouchConfig);
document.getElementById("uploadLogo")?.addEventListener("click", uploadLogoFile);
document.getElementById("removeLogo")?.addEventListener("click", removeLogoFile);
document.getElementById("clearParticipant")?.addEventListener("click", clearParticipantForm);
document.getElementById("clearRule")?.addEventListener("click", clearRuleForm);
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

document.getElementById("testRuleLed")?.addEventListener("click", async () => {
  const ledSettings = readRuleLedSettings();
  setOutput("Testing LED strip...");
  try {
    await api("/api/admin/led/test", {
      method: "POST",
      body: JSON.stringify(ledSettings),
    });
    setOutput(
      `LED test started (${ledSettings.led_flash_duration_seconds}s flash, ${ledSettings.led_flash_interval_ms}ms interval` +
        (ledSettings.led_chase_duration_seconds > 0
          ? `, then ${ledSettings.led_chase_duration_seconds}s chase`
          : "") +
        ").",
    );
  } catch (error) {
    setOutput(error instanceof Error ? error.message : String(error));
  }
});
document.getElementById("participantDate")?.addEventListener("change", loadParticipants);
document.querySelectorAll("[data-pin-digit]").forEach((button) => {
  button.addEventListener("click", () => {
    appendPinDigit(button.dataset.pinDigit || "");
  });
});
document.querySelector("[data-pin-delete]")?.addEventListener("click", deletePinDigit);
document.querySelector("[data-pin-clear]")?.addEventListener("click", clearPinDigits);
document.querySelectorAll("[data-open-keyboard]").forEach((button) => {
  button.addEventListener("click", openKeyboard);
});
savePin?.addEventListener("click", unlock);
pinInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") unlock();
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

document.getElementById("participantDate").value = todayParam;
document.getElementById("importDate").value = todayParam;

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
document.querySelectorAll("[data-scroll-target]").forEach((button) => {
  button.addEventListener("click", () => {
    scrollToPanel(button.dataset.scrollTarget);
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
