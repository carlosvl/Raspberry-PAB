"""SSDP discovery and ECP queries for Roku devices."""

from __future__ import annotations

import logging
import socket
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx

from raspberry_pab.models import RokuDevice

logger = logging.getLogger(__name__)

SSDP_ADDR = ("239.255.255.250", 1900)
SSDP_MX = 2
SSDP_ST = "roku:ecp"
PAB_CHANNEL_NAMES = {"raspberry-pab", "raspberry pab", "pab"}


def _ssdp_search_message() -> bytes:
    return (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}\r\n"
        'MAN: "ssdp:discover"\r\n'
        f"MX: {SSDP_MX}\r\n"
        f"ST: {SSDP_ST}\r\n"
        "\r\n"
    ).encode("ascii")


def parse_ssdp_location(response: bytes) -> str | None:
    """Extract the LOCATION URL from an SSDP response body."""
    text = response.decode("utf-8", errors="replace")
    for line in text.splitlines():
        if line.lower().startswith("location:"):
            return line.split(":", 1)[1].strip()
    return None


def ip_from_location(location: str) -> str | None:
    parsed = urlparse(location)
    host = parsed.hostname
    return host if host else None


def _text(root: ET.Element, tag: str) -> str:
    node = root.find(tag)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def parse_device_info_xml(xml_text: str) -> dict[str, str]:
    root = ET.fromstring(xml_text)
    return {
        "friendly_name": _text(root, "friendly-device-name")
        or _text(root, "user-device-name")
        or _text(root, "friendly-model-name"),
        "model_name": _text(root, "model-name"),
        "serial_number": _text(root, "serial-number"),
    }


def parse_apps_xml(xml_text: str, channel_id: str = "dev") -> bool:
    """Return True if the sideloaded PAB channel id (or name) is installed."""
    root = ET.fromstring(xml_text)
    for app in root.findall("app"):
        app_id = (app.get("id") or "").strip()
        name = (app.text or "").strip().lower()
        if app_id == channel_id:
            return True
        if name in PAB_CHANNEL_NAMES or "raspberry-pab" in name:
            return True
    return False


def parse_active_app_xml(xml_text: str) -> tuple[str, str]:
    root = ET.fromstring(xml_text)
    app = root.find("app")
    if app is None:
        return "", ""
    return (app.get("id") or "").strip(), (app.text or "").strip()


async def query_device(
    ip: str,
    *,
    channel_id: str = "dev",
    timeout: float = 3.0,
) -> RokuDevice:
    """Fetch device-info, apps, and active-app for one Roku IP."""
    base = f"http://{ip}:8060"
    device = RokuDevice(ip=ip)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            info = await client.get(f"{base}/query/device-info")
            if info.status_code == 200:
                parsed = parse_device_info_xml(info.text)
                device.friendly_name = parsed["friendly_name"]
                device.model_name = parsed["model_name"]
                device.serial_number = parsed["serial_number"]
        except httpx.HTTPError:
            logger.debug("device-info failed for %s", ip, exc_info=True)

        try:
            apps = await client.get(f"{base}/query/apps")
            if apps.status_code == 200:
                device.has_pab_channel = parse_apps_xml(apps.text, channel_id)
        except httpx.HTTPError:
            logger.debug("apps query failed for %s", ip, exc_info=True)

        try:
            active = await client.get(f"{base}/query/active-app")
            if active.status_code == 200:
                app_id, app_name = parse_active_app_xml(active.text)
                device.active_app_id = app_id
                device.active_app_name = app_name
        except httpx.HTTPError:
            logger.debug("active-app failed for %s", ip, exc_info=True)

    return device


def discover_roku_ips(*, timeout: float = 3.0) -> list[str]:
    """Blocking SSDP M-SEARCH for roku:ecp; returns unique IPs."""
    found: set[str] = set()
    message = _ssdp_search_message()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.sendto(message, SSDP_ADDR)
        deadline = timeout
        while deadline > 0:
            try:
                data, _addr = sock.recvfrom(65535)
            except TimeoutError:
                break
            except OSError:
                break
            location = parse_ssdp_location(data)
            if location:
                ip = ip_from_location(location)
                if ip:
                    found.add(ip)
    finally:
        sock.close()
    return sorted(found)


async def discover_devices(
    *,
    channel_id: str = "dev",
    ssdp_timeout: float = 3.0,
) -> list[RokuDevice]:
    """SSDP discover Rokus and enrich each with ECP queries."""
    ips = await asyncio_to_thread_discover(ssdp_timeout)
    devices: list[RokuDevice] = []
    for ip in ips:
        try:
            devices.append(await query_device(ip, channel_id=channel_id))
        except Exception:
            logger.exception("Failed to query Roku at %s", ip)
            devices.append(RokuDevice(ip=ip))
    return devices


async def asyncio_to_thread_discover(timeout: float) -> list[str]:
    import asyncio

    return await asyncio.to_thread(discover_roku_ips, timeout=timeout)
