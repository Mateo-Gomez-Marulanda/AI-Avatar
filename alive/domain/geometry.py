"""Geometría pura para anclar el avatar sin depender de GTK."""

from __future__ import annotations

from dataclasses import dataclass

from alive.domain.config import Zone


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


def zone_rect(monitor: Rect, zone: Zone, size: tuple[int, int]) -> Rect:
    width, height = size
    if zone.anchor == "top":
        return Rect((monitor.width - width) // 2, zone.margin, width, height)
    if zone.anchor == "left":
        return Rect(zone.margin, (monitor.height - height) // 2, width, height)
    if zone.anchor == "right":
        return Rect(monitor.width - width - zone.margin, (monitor.height - height) // 2, width, height)
    if zone.anchor == "bottom":
        return Rect((monitor.width - width) // 2, monitor.height - height - zone.margin, width, height)
    if zone.anchor == "bottom-right":
        return Rect(monitor.width - width - zone.margin, monitor.height - height - zone.margin, width, height)
    return Rect(zone.x, zone.y, width, height)


def nearest_zone(
    monitor: Rect,
    pointer: tuple[int, int],
    zones: dict[str, Zone],
    size: tuple[int, int],
) -> str:
    if not zones:
        return "flotante"
    px, py = pointer

    def distance(zone: Zone) -> float:
        rect = zone_rect(monitor, zone, size)
        dx = px - (rect.x + rect.width / 2)
        dy = py - (rect.y + rect.height / 2)
        return dx * dx + dy * dy

    return min(zones, key=lambda name: distance(zones[name]))
