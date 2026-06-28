"""
Real-time system metrics (CPU, RAM, GPU, battery, network).
Exposed as a dataclass updated in the background.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

import psutil
from loguru import logger


@dataclass
class SystemHealth:
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    battery_percent: float | None = None
    battery_plugged: bool = False
    net_sent_mb: float = 0.0
    net_recv_mb: float = 0.0
    disk_percent: float = 0.0
    top_processes: list[dict] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def summary(self) -> str:
        lines = [
            f"CPU {self.cpu_percent:.1f}%",
            f"RAM {self.ram_used_mb:.0f}/{self.ram_total_mb:.0f} MB ({self.ram_percent:.1f}%)",
            f"Disk {self.disk_percent:.1f}%",
        ]
        if self.battery_percent is not None:
            status = "plugged in" if self.battery_plugged else "on battery"
            lines.append(f"Battery {self.battery_percent:.0f}% ({status})")
        return " | ".join(lines)


_health = SystemHealth()


async def _update_loop(interval: float = 5.0) -> None:
    while True:
        try:
            vm = psutil.virtual_memory()
            net = psutil.net_io_counters()
            disk = psutil.disk_usage("/")
            battery = psutil.sensors_battery()

            # Top 5 CPU-consuming processes
            procs: list[dict] = []
            for p in sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]),
                key=lambda x: x.info.get("cpu_percent") or 0,
                reverse=True,
            )[:5]:
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "cpu": p.info.get("cpu_percent", 0),
                    "ram_mb": round((p.info.get("memory_info") or psutil._common.pmem(0, 0)).rss / 1_048_576, 1),
                })

            _health.cpu_percent = psutil.cpu_percent(interval=None)
            _health.ram_percent = vm.percent
            _health.ram_used_mb = vm.used / 1_048_576
            _health.ram_total_mb = vm.total / 1_048_576
            _health.net_sent_mb = net.bytes_sent / 1_048_576
            _health.net_recv_mb = net.bytes_recv / 1_048_576
            _health.disk_percent = disk.percent
            _health.top_processes = procs
            _health.updated_at = datetime.utcnow()

            if battery:
                _health.battery_percent = battery.percent
                _health.battery_plugged = battery.power_plugged
        except Exception:
            logger.exception("System health update failed")

        await asyncio.sleep(interval)


async def start_health_monitor() -> None:
    """Start background health monitoring task."""
    asyncio.create_task(_update_loop(), name="health_monitor")
    logger.debug("System health monitor started.")


def get_system_health() -> SystemHealth:
    """Return the latest cached system health snapshot."""
    return _health
