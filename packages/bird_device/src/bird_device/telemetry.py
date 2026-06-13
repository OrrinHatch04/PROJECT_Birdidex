"""Device telemetry: CPU, memory, temperature.

TODO: Expose a /telemetry endpoint in cyberdeck_ui for remote monitoring.
TODO: Add SD card free space check for long field sessions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeviceTelemetry:
    cpu_percent: float
    memory_percent: float
    cpu_temp_celsius: float | None


def read_telemetry() -> DeviceTelemetry:
    """Read current device telemetry.

    TODO: Add ARM-specific temperature sensors (e.g. /sys/class/thermal).
    """
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        cpu_temp: float | None = None
        for entries in temps.values():
            if entries:
                cpu_temp = entries[0].current
                break
        return DeviceTelemetry(cpu_percent=cpu, memory_percent=mem, cpu_temp_celsius=cpu_temp)
    except ImportError:
        return DeviceTelemetry(cpu_percent=0.0, memory_percent=0.0, cpu_temp_celsius=None)
