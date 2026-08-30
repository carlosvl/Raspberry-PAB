"""Group same-time reminder alerts for sequential hardware playback."""

from __future__ import annotations

import asyncio
from collections import OrderedDict

from raspberry_pab.models import Alert


def alert_slot_key(alert: Alert) -> tuple[int, str]:
    """Same reminder rule + fire time = one playback group."""
    return (alert.rule_id, alert.fire_at.isoformat())


def group_alerts_by_slot(alerts: list[Alert]) -> list[list[Alert]]:
    """Group alerts by (rule_id, fire_at), preserving first-seen slot order."""
    groups: OrderedDict[tuple[int, str], list[Alert]] = OrderedDict()
    for alert in alerts:
        key = alert_slot_key(alert)
        groups.setdefault(key, []).append(alert)
    return list(groups.values())


def drain_alert_queue(
    queue: asyncio.Queue[Alert],
    first: Alert,
) -> list[Alert]:
    """Return first plus any alerts already waiting on the queue."""
    alerts = [first]
    while True:
        try:
            alerts.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return alerts
