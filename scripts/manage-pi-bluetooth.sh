#!/usr/bin/env bash
# Manage Raspberry-PAB Bluetooth speaker via bluetoothctl (JSON for admin UI).
#
# Usage:
#   manage-pi-bluetooth.sh status --json
#   manage-pi-bluetooth.sh scan --json
#   manage-pi-bluetooth.sh paired --json
#   manage-pi-bluetooth.sh pair AA:BB:CC:DD:EE:FF
#   manage-pi-bluetooth.sh connect AA:BB:CC:DD:EE:FF
#   manage-pi-bluetooth.sh disconnect
#   manage-pi-bluetooth.sh forget AA:BB:CC:DD:EE:FF
#
# Prefer running via sudo -n from the admin API.

set -euo pipefail

SCAN_SECONDS="${PAB_BT_SCAN_SECONDS:-12}"
SINK_WAIT_SECONDS="${PAB_BT_SINK_WAIT_SECONDS:-10}"

_json_escape() {
    python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()[:-1] if False else sys.argv[1]))' "$1"
}

_normalize_mac() {
    local mac="$1"
    mac="$(echo "${mac}" | tr '[:lower:]' '[:upper:]' | tr -d ' ')"
    if [[ ! "${mac}" =~ ^([0-9A-F]{2}:){5}[0-9A-F]{2}$ ]]; then
        echo "Invalid MAC address: $1" >&2
        exit 1
    fi
    echo "${mac}"
}

_bt() {
    if [[ "$(id -u)" -eq 0 ]]; then
        bluetoothctl "$@"
    else
        sudo -n bluetoothctl "$@"
    fi
}

_ensure_adapter() {
    if ! command -v bluetoothctl >/dev/null 2>&1; then
        echo "bluetoothctl (bluez) is required." >&2
        exit 1
    fi
    _bt power on >/dev/null 2>&1 || true
    _bt agent on >/dev/null 2>&1 || true
    _bt default-agent >/dev/null 2>&1 || true
}

_audio_uid() {
    if [[ -n "${SUDO_UID:-}" ]]; then
        echo "${SUDO_UID}"
        return 0
    fi
    if [[ -n "${SUDO_USER:-}" ]]; then
        id -u "${SUDO_USER}" 2>/dev/null && return 0
    fi
    if [[ "$(id -u)" -eq 0 ]]; then
        # Prefer the graphical session owner when the script is run via sudo.
        local uid
        uid="$(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}' | while read -r sid; do
            loginctl show-session "${sid}" -p Name -p Display -p Type -p Remote 2>/dev/null \
                | awk -F= '
                    $1=="Name"{u=$2}
                    $1=="Display"{d=$2}
                    $1=="Type"{t=$2}
                    $1=="Remote"{r=$2}
                    END{if(u!="" && r!="yes" && (d!="" || t=="wayland" || t=="x11")) print u}
                '
        done | head -1)"
        if [[ -n "${uid}" ]]; then
            id -u "${uid}" 2>/dev/null && return 0
        fi
        if [[ -d /run/user/1000 ]]; then
            echo 1000
            return 0
        fi
    fi
    id -u
}

_pactl_env() {
    local uid
    uid="$(_audio_uid)"
    export XDG_RUNTIME_DIR="/run/user/${uid}"
}

_pactl() {
    _pactl_env
    local pactl_bin=""
    if command -v pactl >/dev/null 2>&1; then
        pactl_bin="$(command -v pactl)"
    elif [[ -x /usr/bin/pactl ]]; then
        pactl_bin=/usr/bin/pactl
    else
        return 1
    fi
    # Always talk to the desktop user's PipeWire/Pulse, not root's.
    if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
        sudo -n -u "${SUDO_USER}" env XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" "${pactl_bin}" "$@"
    elif [[ "$(id -u)" -eq 0 ]]; then
        local user
        user="$(getent passwd "$(_audio_uid)" | cut -d: -f1)"
        if [[ -n "${user}" ]]; then
            sudo -n -u "${user}" env XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" "${pactl_bin}" "$@"
        else
            env XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" "${pactl_bin}" "$@"
        fi
    else
        env XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" "${pactl_bin}" "$@"
    fi
}

_list_sinks() {
    _pactl list short sinks 2>/dev/null || true
}

_ensure_a2dp_profile() {
    local mac="$1"
    local compact card line
    compact="$(echo "${mac}" | tr -d ':' | tr '[:upper:]' '[:lower:]')"
    while IFS= read -r line; do
        # shellcheck disable=SC2206
        local parts=(${line})
        [[ ${#parts[@]} -lt 2 ]] && continue
        card="${parts[1]}"
        local lower
        lower="$(echo "${card}" | tr '[:upper:]' '[:lower:]')"
        if [[ "${lower}" == bluez_card* ]] && [[ "${lower}" == *"${compact}"* || "${compact}" == "" ]]; then
            _pactl set-card-profile "${card}" a2dp-sink >/dev/null 2>&1 \
                || _pactl set-card-profile "${card}" a2dp_sink >/dev/null 2>&1 \
                || true
            return 0
        fi
    done < <(_pactl list short cards 2>/dev/null || true)
    # Fallback: first bluez card
    while IFS= read -r line; do
        # shellcheck disable=SC2206
        local parts=(${line})
        [[ ${#parts[@]} -lt 2 ]] && continue
        card="${parts[1]}"
        if [[ "$(echo "${card}" | tr '[:upper:]' '[:lower:]')" == bluez_card* ]]; then
            _pactl set-card-profile "${card}" a2dp-sink >/dev/null 2>&1 \
                || _pactl set-card-profile "${card}" a2dp_sink >/dev/null 2>&1 \
                || true
            return 0
        fi
    done < <(_pactl list short cards 2>/dev/null || true)
}

_bluez_sink_for_mac() {
    local mac="$1"
    local compact
    compact="$(echo "${mac}" | tr -d ':' | tr '[:upper:]' '[:lower:]')"
    while IFS= read -r line; do
        # shellcheck disable=SC2206
        local parts=(${line})
        [[ ${#parts[@]} -lt 2 ]] && continue
        local name="${parts[1]}"
        local lower
        lower="$(echo "${name}" | tr '[:upper:]' '[:lower:]')"
        if [[ "${lower}" == bluez_output* ]] && [[ "${lower}" == *"${compact}"* ]]; then
            echo "${name}"
            return 0
        fi
    done < <(_list_sinks)
    # Fallback: first bluez sink if MAC not embedded in name.
    while IFS= read -r line; do
        # shellcheck disable=SC2206
        local parts=(${line})
        [[ ${#parts[@]} -lt 2 ]] && continue
        local name="${parts[1]}"
        if [[ "$(echo "${name}" | tr '[:upper:]' '[:lower:]')" == bluez_output* ]]; then
            echo "${name}"
            return 0
        fi
    done < <(_list_sinks)
    return 1
}

_wait_for_bluez_sink() {
    local mac="$1"
    local i sink=""
    for ((i = 0; i < SINK_WAIT_SECONDS; i++)); do
        _ensure_a2dp_profile "${mac}" || true
        if sink="$(_bluez_sink_for_mac "${mac}" 2>/dev/null)"; then
            echo "${sink}"
            return 0
        fi
        sleep 1
    done
    return 1
}

_device_connected() {
    local mac="$1"
    _bt info "${mac}" 2>/dev/null | grep -q "Connected: yes"
}

_connected_mac() {
    local mac
    mac="$(_bt devices Connected 2>/dev/null | awk '{print $2; exit}' || true)"
    if [[ -n "${mac}" ]]; then
        echo "${mac}"
        return 0
    fi
    while IFS= read -r line; do
        mac="$(echo "${line}" | awk '{print $2}')"
        [[ -z "${mac}" ]] && continue
        if _device_connected "${mac}"; then
            echo "${mac}"
            return 0
        fi
    done < <(_bt devices 2>/dev/null || true)
}

_device_info_line() {
    # Output: MAC|Name|Paired|Trusted|Connected
    local mac="$1"
    local info
    info="$(_bt info "${mac}" 2>/dev/null || true)"
    local name paired trusted connected
    name="$(echo "${info}" | awk -F': ' '/^\tName:/ {print $2; exit}')"
    [[ -z "${name}" ]] && name="$(echo "${info}" | awk -F': ' '/^\tAlias:/ {print $2; exit}')"
    paired="false"
    trusted="false"
    connected="false"
    echo "${info}" | grep -q "Paired: yes" && paired="true"
    echo "${info}" | grep -q "Trusted: yes" && trusted="true"
    echo "${info}" | grep -q "Connected: yes" && connected="true"
    printf '%s|%s|%s|%s|%s\n' "${mac}" "${name:-}" "${paired}" "${trusted}" "${connected}"
}

cmd_status() {
    _ensure_adapter
    local powered="false"
    if _bt show 2>/dev/null | grep -q "Powered: yes"; then
        powered="true"
    fi
    local mac name paired trusted connected sink=""
    mac="$(_connected_mac || true)"
    connected="false"
    paired="false"
    trusted="false"
    name=""
    if [[ -n "${mac}" ]]; then
        IFS='|' read -r mac name paired trusted connected <<< "$(_device_info_line "${mac}")"
        sink="$(_bluez_sink_for_mac "${mac}" 2>/dev/null || true)"
    fi
    PAB_BT_POWERED="${powered}" \
    PAB_BT_CONNECTED="${connected:-false}" \
    PAB_BT_PAIRED="${paired:-false}" \
    PAB_BT_TRUSTED="${trusted:-false}" \
    PAB_BT_MAC="${mac}" \
    PAB_BT_NAME="${name}" \
    PAB_BT_SINK="${sink}" \
    python3 - <<'PY'
import json, os
def flag(key: str) -> bool:
    return os.environ.get(key, "false").lower() in ("1", "true", "yes")
def text(key: str):
    value = os.environ.get(key, "").strip()
    return value or None
print(json.dumps({
    "powered": flag("PAB_BT_POWERED"),
    "connected": flag("PAB_BT_CONNECTED"),
    "paired": flag("PAB_BT_PAIRED"),
    "trusted": flag("PAB_BT_TRUSTED"),
    "mac": text("PAB_BT_MAC"),
    "name": text("PAB_BT_NAME"),
    "sink": text("PAB_BT_SINK"),
}))
PY
}

cmd_paired() {
    _ensure_adapter
    python3 - <<'PY'
import json, subprocess, os

def bt(*args):
    cmd = ["bluetoothctl", *args]
    if os.geteuid() != 0:
        cmd = ["sudo", "-n", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout

def friendly_name(mac: str, info: str, fallback: str = "") -> str:
    import re
    candidates = []
    for prefix in ("\tName: ", "\tAlias: "):
        for row in info.splitlines():
            if row.startswith(prefix):
                candidates.append(row[len(prefix):].strip())
    if fallback:
        candidates.append(fallback.strip())
    mac_c = re.sub(r"[^0-9A-Fa-f]", "", mac or "").upper()
    for value in candidates:
        if not value:
            continue
        if re.sub(r"[^0-9A-Fa-f]", "", value).upper() == mac_c:
            continue
        return value
    return ""

devices = []
for line in bt("devices").splitlines():
    parts = line.split(maxsplit=2)
    if len(parts) < 2:
        continue
    mac = parts[1]
    listed = parts[2] if len(parts) > 2 else ""
    info = bt("info", mac)
    if "Paired: yes" not in info and "Trusted: yes" not in info:
        continue
    name = friendly_name(mac, info, listed)
    devices.append({
        "mac": mac,
        "name": name or mac,
        "paired": "Paired: yes" in info,
        "trusted": "Trusted: yes" in info,
        "connected": "Connected: yes" in info,
    })
devices.sort(key=lambda d: (d["name"].lower(), d["mac"]))
print(json.dumps({"devices": devices}))
PY
}

cmd_scan() {
    _ensure_adapter
    # Non-interactive "scan on" returns immediately and often finds nothing.
    # --timeout keeps discovery active for the full window.
    _bt --timeout "${SCAN_SECONDS}" scan on >/dev/null 2>&1 || true
    _bt scan off >/dev/null 2>&1 || true
    python3 - <<'PY'
import json, re, subprocess, os

def bt(*args):
    cmd = ["bluetoothctl", *args]
    if os.geteuid() != 0:
        cmd = ["sudo", "-n", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout

def mac_compact(value: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", value or "").upper()

def friendly_name(mac: str, info: str, fallback: str = "") -> str:
    candidates = []
    for prefix in ("\tName: ", "\tAlias: "):
        for row in info.splitlines():
            if row.startswith(prefix):
                candidates.append(row[len(prefix):].strip())
    if fallback:
        candidates.append(fallback.strip())
    mac_c = mac_compact(mac)
    for value in candidates:
        if not value:
            continue
        if mac_compact(value) == mac_c:
            continue
        return value
    return ""

def is_audio_device(info: str) -> bool:
    lower = info.lower()
    markers = (
        "uuid: audio sink",
        "uuid: audio source",
        "uuid: a/v remote",
        "uuid: advanced audio",
        "icon: audio",
        "class: 0x240",  # common audio major class prefix variants
        "class: 0x200",
    )
    if any(m in lower for m in markers):
        return True
    # CoD bit for Audio (Major Service Class / Major Device Class)
    for row in info.splitlines():
        if row.strip().startswith("Class:"):
            # e.g. Class: 0x00240414
            if "Audio" in row or "Headset" in row or "Loudspeaker" in row:
                return True
            m = re.search(r"0x([0-9a-fA-F]+)", row)
            if m:
                try:
                    cod = int(m.group(1), 16)
                except ValueError:
                    continue
                major = (cod >> 8) & 0x1F
                if major == 0x04:  # Audio/Video
                    return True
    return False

devices = []
seen = set()
for line in bt("devices").splitlines():
    parts = line.split(maxsplit=2)
    if len(parts) < 2:
        continue
    mac = parts[1]
    if mac in seen:
        continue
    seen.add(mac)
    listed = parts[2] if len(parts) > 2 else ""
    info = bt("info", mac)
    name = friendly_name(mac, info, listed)
    audio = is_audio_device(info)
    devices.append({
        "mac": mac,
        "name": name or "Unknown device",
        "paired": "Paired: yes" in info,
        "trusted": "Trusted: yes" in info,
        "connected": "Connected: yes" in info,
        "audio": audio,
    })

# Prefer named speakers, then any named device, then the rest.
devices.sort(
    key=lambda d: (
        0 if (d["audio"] and d["name"] != "Unknown device") else
        1 if d["name"] != "Unknown device" else
        2 if d["audio"] else 3,
        d["name"].lower(),
        d["mac"],
    )
)
print(json.dumps({"devices": devices}))
PY
}

cmd_pair() {
    local mac
    mac="$(_normalize_mac "$1")"
    _ensure_adapter
    _bt pairable on >/dev/null 2>&1 || true
    _bt scan on >/dev/null 2>&1 || true
    sleep 2
    if ! _bt pair "${mac}"; then
        _bt scan off >/dev/null 2>&1 || true
        echo "Failed to pair ${mac}" >&2
        exit 1
    fi
    _bt trust "${mac}" >/dev/null 2>&1 || true
    _bt scan off >/dev/null 2>&1 || true
    python3 - <<PY
import json
print(json.dumps({"ok": True, "mac": "${mac}", "paired": True, "trusted": True}))
PY
}

cmd_connect() {
    local mac
    mac="$(_normalize_mac "$1")"
    _ensure_adapter
    _bt trust "${mac}" >/dev/null 2>&1 || true
    local already=false
    if _device_connected "${mac}"; then
        already=true
    else
        local connect_out=""
        if ! connect_out="$(_bt connect "${mac}" 2>&1)"; then
            # Already linked at ACL / busy often still means usable; continue to A2DP.
            if _device_connected "${mac}" || echo "${connect_out}" | grep -qiE 'br-connection-busy|Already Connected|InProgress'; then
                already=true
            else
                echo "${connect_out}" >&2
                echo "Failed to connect ${mac}" >&2
                exit 1
            fi
        fi
    fi
    local sink=""
    sink="$(_wait_for_bluez_sink "${mac}" || true)"
    local name=""
    name="$(_bt info "${mac}" 2>/dev/null | awk -F': ' '
        /^\tName:/ { name=$2; exit }
        /^\tAlias:/ { if (alias=="") alias=$2 }
        END { if (name != "") print name; else if (alias != "") print alias }
    ')"
    PAB_BT_MAC="${mac}" PAB_BT_NAME="${name}" PAB_BT_SINK="${sink}" python3 - <<'PY'
import json, os
def text(key: str):
    value = os.environ.get(key, "").strip()
    return value or None
print(json.dumps({
    "ok": True,
    "mac": text("PAB_BT_MAC"),
    "name": text("PAB_BT_NAME"),
    "connected": True,
    "sink": text("PAB_BT_SINK"),
}))
PY
}

cmd_disconnect() {
    _ensure_adapter
    local mac
    mac="$(_connected_mac || true)"
    if [[ -n "${mac}" ]]; then
        _bt disconnect "${mac}" >/dev/null 2>&1 || true
    fi
    PAB_BT_MAC="${mac}" python3 - <<'PY'
import json, os
mac = os.environ.get("PAB_BT_MAC", "").strip() or None
print(json.dumps({"ok": True, "disconnected": True, "mac": mac}))
PY
}

cmd_forget() {
    local mac
    mac="$(_normalize_mac "$1")"
    _ensure_adapter
    _bt disconnect "${mac}" >/dev/null 2>&1 || true
    _bt remove "${mac}" >/dev/null 2>&1 || true
    python3 - <<PY
import json
print(json.dumps({"ok": True, "forgotten": "${mac}"}))
PY
}

usage() {
    cat >&2 <<EOF
Usage: $0 {status|scan|paired|pair|connect|disconnect|forget} ...
EOF
    exit 2
}

main() {
    local cmd="${1:-}"
    shift || true
    case "${cmd}" in
        status) cmd_status "$@" ;;
        scan) cmd_scan "$@" ;;
        paired) cmd_paired "$@" ;;
        pair)
            [[ $# -ge 1 ]] || usage
            cmd_pair "$1"
            ;;
        connect)
            [[ $# -ge 1 ]] || usage
            cmd_connect "$1"
            ;;
        disconnect) cmd_disconnect "$@" ;;
        forget)
            [[ $# -ge 1 ]] || usage
            cmd_forget "$1"
            ;;
        *) usage ;;
    esac
}

main "$@"
