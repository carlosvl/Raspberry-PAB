#!/usr/bin/env bash
# Manage Raspberry-PAB Wi-Fi via NetworkManager (JSON-friendly for admin UI).
#
# Usage:
#   manage-pi-wifi.sh status --json
#   manage-pi-wifi.sh saved --json
#   manage-pi-wifi.sh scan --json
#   manage-pi-wifi.sh connect "SSID" [password]
#   manage-pi-wifi.sh connect-saved "NAME"
#   manage-pi-wifi.sh forget "NAME"
#
# When run as root (via sudo -n), nmcli calls omit sudo.

set -euo pipefail

HOTSPOT_CONNECTION="${PAB_HOTSPOT_CONNECTION:-PAB-Hotspot}"
IFACE="${PAB_HOTSPOT_IFACE:-wlan0}"
HOTSPOT_WAS_ACTIVE=0

_nm() {
    # Cap activation waits so a bad PSK cannot hang forever (and leave the
    # fallback hotspot down, killing SSH on 10.42.0.1).
    if [[ "$(id -u)" -eq 0 ]]; then
        nmcli -w 25 "$@"
    else
        sudo -n nmcli -w 25 "$@"
    fi
}

_systemctl() {
    if [[ "$(id -u)" -eq 0 ]]; then
        systemctl "$@"
    else
        sudo -n systemctl "$@"
    fi
}

if ! command -v nmcli >/dev/null 2>&1; then
    echo "nmcli (NetworkManager) is required." >&2
    exit 1
fi

_current_connection() {
    nmcli -t -f GENERAL.CONNECTION device show "${IFACE}" 2>/dev/null \
        | awk -F: '{ print $2 }' \
        | tr -d ' '
}

_current_ssid() {
    nmcli -t -f GENERAL.CONNECTION,802-11-wireless.ssid connection show "$1" 2>/dev/null \
        | awk -F: '/802-11-wireless.ssid:/ { print $2; exit }'
}

_iface_ipv4() {
    ip -4 -o addr show "${IFACE}" 2>/dev/null \
        | awk '{ print $4 }' \
        | head -n 1 \
        | cut -d/ -f1 \
        || true
}

_stop_hotspot_for_scan() {
    if [[ "$(_current_connection)" == "${HOTSPOT_CONNECTION}" ]]; then
        HOTSPOT_WAS_ACTIVE=1
    fi
    _systemctl stop pab-autohotspot.timer 2>/dev/null || true
    _nm connection down "${HOTSPOT_CONNECTION}" >/dev/null 2>&1 || true
    _nm radio wifi on >/dev/null 2>&1 || true
    sleep 2
}

_restore_hotspot() {
    if [[ "${HOTSPOT_WAS_ACTIVE}" != "1" ]]; then
        return 0
    fi
    _nm connection up "${HOTSPOT_CONNECTION}" ifname "${IFACE}" >/dev/null 2>&1 \
        || /usr/local/bin/pab-autohotspot 2>/dev/null \
        || true
    _systemctl start pab-autohotspot.timer 2>/dev/null || true
}

_cmd_status() {
    local connection ssid ipv4 on_hotspot state
    connection="$(_current_connection)"
    state="$(nmcli -t -f GENERAL.STATE device show "${IFACE}" 2>/dev/null | awk -F: '{ print $2 }' || true)"
    ipv4="$(_iface_ipv4)"
    on_hotspot="false"
    ssid=""
    if [[ "${connection}" == "${HOTSPOT_CONNECTION}" ]]; then
        on_hotspot="true"
        ssid="${PAB_HOTSPOT_SSID:-Raspberry-PAB}"
    elif [[ -n "${connection}" ]]; then
        ssid="$(_current_ssid "${connection}")"
        if [[ -z "${ssid}" ]]; then
            ssid="${connection}"
        fi
    fi

    python3 - <<PY
import json
print(json.dumps({
    "iface": ${IFACE@Q},
    "connection": ${connection@Q},
    "ssid": ${ssid@Q},
    "ipv4": ${ipv4@Q},
    "on_hotspot": json.loads(${on_hotspot@Q}),
    "state": ${state@Q},
    "hotspot_connection": ${HOTSPOT_CONNECTION@Q},
}, separators=(",", ":")))
PY
}

_cmd_saved() {
    HOTSPOT_CONNECTION="${HOTSPOT_CONNECTION}" python3 - <<'PY'
import json
import os
import subprocess

hotspot = os.environ.get("HOTSPOT_CONNECTION", "PAB-Hotspot")

raw = subprocess.check_output(
    ["nmcli", "-t", "-f", "NAME,TYPE,UUID", "connection", "show"],
    text=True,
    errors="replace",
)
networks = []
for line in raw.splitlines():
    if not line.strip():
        continue
    parts = line.split(":")
    if len(parts) < 3:
        continue
    name, ctype, uuid = parts[0], parts[1], parts[2]
    if ctype != "802-11-wireless":
        continue
    if name == hotspot:
        continue
    ssid = name
    security = ""
    try:
        detail = subprocess.check_output(
            ["nmcli", "-t", "-f", "802-11-wireless.ssid,802-11-wireless-security.key-mgmt", "connection", "show", name],
            text=True,
            errors="replace",
        )
        for dline in detail.splitlines():
            key, _, value = dline.partition(":")
            if key == "802-11-wireless.ssid" and value:
                ssid = value
            elif key == "802-11-wireless-security.key-mgmt":
                security = value
    except subprocess.CalledProcessError:
        pass
    networks.append({
        "name": name,
        "ssid": ssid,
        "uuid": uuid,
        "security": security,
    })
print(json.dumps({"networks": networks}, separators=(",", ":")))
PY
}

_cmd_scan() {
    _stop_hotspot_for_scan
    _nm device wifi rescan ifname "${IFACE}" >/dev/null 2>&1 \
        || nmcli device wifi rescan >/dev/null 2>&1 \
        || true
    sleep 3
    local list_out
    list_out="$(nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list ifname "${IFACE}" 2>/dev/null \
        || nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list)"
    _restore_hotspot

    NETWORKS_RAW="${list_out}" python3 - <<'PY'
import json
import os

raw = os.environ.get("NETWORKS_RAW", "")
seen = set()
networks = []
for line in raw.splitlines():
    if not line.strip():
        continue
    # nmcli -t uses : as separator; SSID can contain :
    parts = line.split(":")
    if len(parts) < 4:
        continue
    in_use = parts[0]
    security = parts[-1]
    signal = parts[-2]
    ssid = ":".join(parts[1:-2])
    if not ssid or ssid in seen:
        continue
    seen.add(ssid)
    try:
        signal_int = int(signal)
    except ValueError:
        signal_int = 0
    networks.append({
        "ssid": ssid,
        "signal": signal_int,
        "security": security,
        "in_use": in_use == "*",
        "secured": bool(security and security.upper() not in {"", "--", "NONE"}),
    })
networks.sort(key=lambda item: (-item["signal"], item["ssid"].lower()))
print(json.dumps({"networks": networks}, separators=(",", ":")))
PY
}

_find_connection_for_ssid() {
    local target="$1"
    local name ctype ssid
    while IFS=: read -r name ctype; do
        [[ "${ctype}" == "802-11-wireless" ]] || continue
        [[ "${name}" == "${HOTSPOT_CONNECTION}" ]] && continue
        ssid="$(nmcli -t -f 802-11-wireless.ssid connection show "${name}" 2>/dev/null \
            | awk -F: '{ print substr($0, index($0,$2)) }')"
        if [[ "${ssid}" == "${target}" || "${name}" == "${target}" ]]; then
            printf '%s\n' "${name}"
            return 0
        fi
    done < <(nmcli -t -f NAME,TYPE connection show 2>/dev/null)
    return 1
}

_apply_psk_and_up() {
    local name="$1"
    local password="$2"
    local out=""

    # Prefer updating the saved profile. nmcli device wifi connect … password …
    # often fails on NM 1.5x with existing profiles ("password not given in
    # 'password-file'").
    if [[ -n "${password}" ]]; then
        out="$(_nm connection modify "${name}" \
            802-11-wireless-security.key-mgmt wpa-psk \
            802-11-wireless-security.psk "${password}" 2>&1)" || {
            echo "${out}" >&2
            return 1
        }
    fi
    out="$(_nm connection up "${name}" ifname "${IFACE}" 2>&1)" || {
        echo "${out}" >&2
        return 1
    }
    printf '%s\n' "${out}"
    return 0
}

_cmd_connect() {
    local ssid="${1:-}"
    local password="${2:-}"
    if [[ -z "${ssid}" ]]; then
        echo "Usage: manage-pi-wifi.sh connect \"SSID\" [password]" >&2
        exit 1
    fi

    _stop_hotspot_for_scan
    _nm device wifi rescan ifname "${IFACE}" >/dev/null 2>&1 || true
    sleep 2

    set +e
    local connect_out connect_rc=1 existing=""
    existing="$(_find_connection_for_ssid "${ssid}" || true)"

    if [[ -n "${existing}" ]]; then
        connect_out="$(_apply_psk_and_up "${existing}" "${password}" 2>&1)"
        connect_rc=$?
    elif [[ -n "${password}" ]]; then
        # Create/activate a fresh WPA profile for this SSID.
        connect_out="$(_nm connection add type wifi con-name "${ssid}" ifname "${IFACE}" \
            ssid "${ssid}" \
            wifi-sec.key-mgmt wpa-psk \
            wifi-sec.psk "${password}" 2>&1)"
        connect_rc=$?
        if [[ "${connect_rc}" == "0" ]]; then
            connect_out="$(_nm connection up "${ssid}" ifname "${IFACE}" 2>&1)"
            connect_rc=$?
        fi
        # Fallback for older NM behavior.
        if [[ "${connect_rc}" != "0" ]]; then
            connect_out="$(_nm device wifi connect "${ssid}" password "${password}" ifname "${IFACE}" 2>&1)"
            connect_rc=$?
        fi
    else
        connect_out="$(_nm device wifi connect "${ssid}" ifname "${IFACE}" 2>&1)"
        connect_rc=$?
    fi
    set -e

    if [[ "${connect_rc}" != "0" ]]; then
        echo "${connect_out}" >&2
        _restore_hotspot
        exit 1
    fi

    _systemctl start pab-autohotspot.timer 2>/dev/null || true
    local connection ipv4
    connection="$(_current_connection)"
    ipv4="$(_iface_ipv4)"
    python3 - <<PY
import json
print(json.dumps({
    "ok": True,
    "ssid": ${ssid@Q},
    "connection": ${connection@Q},
    "ipv4": ${ipv4@Q},
    "message": ${connect_out@Q},
}, separators=(",", ":")))
PY
}

_cmd_connect_saved() {
    local name="${1:-}"
    if [[ -z "${name}" ]]; then
        echo "Usage: manage-pi-wifi.sh connect-saved \"NAME\"" >&2
        exit 1
    fi
    if [[ "${name}" == "${HOTSPOT_CONNECTION}" ]]; then
        echo "Cannot connect-saved the fallback hotspot profile from admin WiFi." >&2
        exit 1
    fi

    _stop_hotspot_for_scan
    set +e
    local out rc
    out="$(_nm connection up "${name}" ifname "${IFACE}" 2>&1)"
    rc=$?
    set -e
    if [[ "${rc}" != "0" ]]; then
        echo "${out}" >&2
        echo "Saved network failed to connect (wrong password or out of range). Re-enter the password under Connect, or Forget and add it again." >&2
        _restore_hotspot
        exit 1
    fi
    _systemctl start pab-autohotspot.timer 2>/dev/null || true
    local connection ipv4 ssid
    connection="$(_current_connection)"
    ipv4="$(_iface_ipv4)"
    ssid="$(_current_ssid "${connection}")"
    if [[ -z "${ssid}" ]]; then
        ssid="${connection}"
    fi
    python3 - <<PY
import json
print(json.dumps({
    "ok": True,
    "name": ${name@Q},
    "ssid": ${ssid@Q},
    "connection": ${connection@Q},
    "ipv4": ${ipv4@Q},
    "message": ${out@Q},
}, separators=(",", ":")))
PY
}

_cmd_forget() {
    local name="${1:-}"
    if [[ -z "${name}" ]]; then
        echo "Usage: manage-pi-wifi.sh forget \"NAME\"" >&2
        exit 1
    fi
    if [[ "${name}" == "${HOTSPOT_CONNECTION}" ]]; then
        echo "Refusing to delete the fallback hotspot profile ${HOTSPOT_CONNECTION}." >&2
        exit 1
    fi
    _nm connection delete "${name}" >/dev/null
    python3 - <<PY
import json
print(json.dumps({"ok": True, "forgotten": ${name@Q}}, separators=(",", ":")))
PY
}

COMMAND="${1:-}"
shift || true

case "${COMMAND}" in
    status)
        _cmd_status
        ;;
    saved)
        _cmd_saved
        ;;
    scan)
        _cmd_scan
        ;;
    connect)
        _cmd_connect "$@"
        ;;
    connect-saved)
        _cmd_connect_saved "$@"
        ;;
    forget)
        _cmd_forget "$@"
        ;;
    *)
        echo "Usage: $(basename "$0") {status|saved|scan|connect|connect-saved|forget} ..." >&2
        exit 1
        ;;
esac
