"""Helpers for discovering the Pi's LAN addresses and URLs."""

from __future__ import annotations

import socket

HOTSPOT_IPV4 = "10.42.0.1"


def local_ipv4_addresses() -> list[str]:
    """Return non-loopback IPv4 addresses visible on this host."""
    addresses: set[str] = set()
    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None):
            if family == socket.AF_INET:
                address = sockaddr[0]
                if isinstance(address, str) and not address.startswith("127."):
                    addresses.add(address)
    except socket.gaierror:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            address = sock.getsockname()[0]
            if isinstance(address, str) and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    return sorted(addresses)


def lan_base_urls(port: int) -> list[str]:
    """HTTP base URLs for each LAN IPv4 address."""
    return [f"http://{address}:{port}" for address in local_ipv4_addresses()]


def preferred_lan_base_url(port: int) -> str | None:
    """Prefer the hotspot address when present, otherwise the first LAN URL."""
    urls = lan_base_urls(port)
    hotspot = f"http://{HOTSPOT_IPV4}:{port}"
    if hotspot in urls:
        return hotspot
    if urls:
        return urls[0]
    return None
