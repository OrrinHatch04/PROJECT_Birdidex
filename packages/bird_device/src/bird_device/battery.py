"""Battery telemetry stub.

TODO: Implement using psutil on Linux/Raspberry Pi.
TODO: Expose low-battery warnings to the cyberdeck UI via an event bus.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BatteryState:
    percent: float
    plugged: bool
    seconds_remaining: int | None


def read_battery() -> BatteryState | None:
    """Return current battery state or None if not available.

    TODO: On cyberdeck hardware read via psutil.sensors_battery().
    """
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return None
        return BatteryState(
            percent=b.percent,
            plugged=b.power_plugged,
            seconds_remaining=int(b.secsleft) if b.secsleft > 0 else None,
        )
    except ImportError:
        return None
