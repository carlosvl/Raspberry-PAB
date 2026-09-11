"""Roku External Control Protocol (ECP) helpers."""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


def launch_url(
    ip: str,
    *,
    channel_id: str,
    content_id: str,
    port: int = 8060,
) -> str:
    """Build the ECP launch URL for the sideloaded PAB channel."""
    encoded = quote(content_id, safe="")
    return f"http://{ip}:{port}/launch/{channel_id}?contentId={encoded}"


async def launch_channel(
    ip: str,
    *,
    channel_id: str,
    content_id: str,
    port: int = 8060,
    timeout: float = 5.0,
) -> None:
    """POST /launch/{channelId}?contentId=... to start the PAB board."""
    url = launch_url(ip, channel_id=channel_id, content_id=content_id, port=port)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url)
        response.raise_for_status()
    logger.info("Launched Roku channel %s on %s with %s", channel_id, ip, content_id)


async def send_home(ip: str, *, port: int = 8060, timeout: float = 5.0) -> None:
    """Send the Home keypress to leave the PAB channel."""
    url = f"http://{ip}:{port}/keypress/Home"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url)
        response.raise_for_status()
    logger.info("Sent Home to Roku %s", ip)
