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
const remoteInfoEl = document.getElementById("remoteInfo");

const todayParam = new Date().toISOString().slice(0, 10);

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
}

function renderNetworkInfo(info) {
  if (!remoteInfoEl) return;
  const url = info.urls?.[0] || info.hotspot_url;
  remoteInfoEl.textContent = url
    ? `Remote: ${url}/admin or ${info.mdns_name}:${info.port}/admin`
    : "Remote access unavailable";
}

async function loadNetworkInfo() {
  try {
    const response = await fetch("/api/network");
    if (!response.ok) throw new Error("network request failed");
    renderNetworkInfo(await response.json());
  } catch {
    if (remoteInfoEl) remoteInfoEl.textContent = "Remote access unavailable";
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

async function openKeyboard() {
  setPinMessage("Opening keyboard...");
  try {
    const response = await fetch("/api/kiosk/keyboard", { method: "POST" });
    if (!response.ok) throw new Error("keyboard request failed");
    setPinMessage("Keyboard opened.");
    setOutput("Keyboard opened.");
  } catch {
    setPinMessage("Keyboard is not available on this display.");
    setOutput("Keyboard is not available on this display.");
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
          <strong>${item.name}</strong>
          <span>${item.event_date} ${item.start_time}</span>
          <button data-edit-participant="${item.id}" type="button">Edit</button>
          <button data-delete-participant="${item.id}" type="button">Delete</button>
        </div>
      `,
    )
    .join("");

  participantList.querySelectorAll("[data-edit-participant]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = participants.find(
        (participant) => participant.id === Number(button.dataset.editParticipant),
      );
      if (!item) return;
      document.getElementById("participantId").value = item.id;
      document.getElementById("participantName").value = item.name;
      document.getElementById("participantDate").value = item.event_date;
      document.getElementById("participantTime").value = item.start_time.slice(0, 5);
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
  if (!ruleList) return;
  ruleList.innerHTML = rules
    .map(
      (rule) => `
        <div class="admin__item">
          <strong>${rule.offset_minutes} min: ${rule.message_template}</strong>
          <span>${rule.repeat_every_minutes ? `Repeats every ${rule.repeat_every_minutes} min` : "One time"} · ${rule.enabled ? "Enabled" : "Disabled"}</span>
          <button data-edit-rule="${rule.id}" type="button">Edit</button>
          <button data-delete-rule="${rule.id}" type="button">Delete</button>
        </div>
      `,
    )
    .join("");

  ruleList.querySelectorAll("[data-edit-rule]").forEach((button) => {
    button.addEventListener("click", () => {
      const rule = rules.find((item) => item.id === Number(button.dataset.editRule));
      if (!rule) return;
      document.getElementById("ruleId").value = rule.id;
      document.getElementById("ruleOffset").value = rule.offset_minutes;
      document.getElementById("ruleMessage").value = rule.message_template;
      document.getElementById("ruleRepeat").value = rule.repeat_every_minutes || "";
      document.getElementById("ruleEnabled").checked = rule.enabled;
    });
  });

  ruleList.querySelectorAll("[data-delete-rule]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/reminder-rules/${button.dataset.deleteRule}`, {
        method: "DELETE",
      });
      await loadRules();
    });
  });
}

async function loadAll() {
  try {
    await Promise.all([loadParticipants(), loadRules()]);
    setOutput("Loaded.");
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
    setOutput(error.message);
  }
});

document.getElementById("clearParticipant")?.addEventListener("click", clearParticipantForm);
document.getElementById("clearRule")?.addEventListener("click", clearRuleForm);
document.getElementById("participantDate")?.addEventListener("change", loadParticipants);
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

document.getElementById("participantDate").value = todayParam;
document.getElementById("importDate").value = todayParam;
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
