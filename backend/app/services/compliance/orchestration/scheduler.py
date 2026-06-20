"""
Scheduling orchestrator — manages device polling schedules and timing.
Determines which devices are due for polling based on next_poll_at timestamps.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Callable

import structlog

log = structlog.get_logger(__name__)


class PollScheduler:
    """
    Async-safe scheduler — tracks device poll timing, determines due devices.
    Does NOT execute polls; just manages the schedule.
    """

    def __init__(self, check_interval: int = 10) -> None:
        """
        Args:
            check_interval: Seconds between schedule checks (default 10s).
        """
        self._check_interval = check_interval
        self._devices: dict[str, datetime] = {}  # device_id → next_poll_at
        self._lock = asyncio.Lock()

    async def register(self, device_id: str, poll_at: datetime | None = None) -> None:
        """Register device for scheduling."""
        async with self._lock:
            self._devices[device_id] = poll_at or datetime.now(timezone.utc)
            log.debug("scheduler.device.registered", device_id=device_id)

    async def deregister(self, device_id: str) -> None:
        """Remove device from scheduler."""
        async with self._lock:
            self._devices.pop(device_id, None)
            log.debug("scheduler.device.deregistered", device_id=device_id)

    async def reschedule(self, device_id: str, poll_at: datetime) -> None:
        """Update device's next poll time."""
        async with self._lock:
            if device_id in self._devices:
                self._devices[device_id] = poll_at
                log.debug("scheduler.device.rescheduled", device_id=device_id, next_at=poll_at.isoformat())

    async def get_due_devices(self) -> list[str]:
        """Return list of device IDs that are due for polling now."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            return [did for did, poll_at in self._devices.items() if poll_at <= now]

    async def run_scheduler_loop(
        self,
        on_due: Callable[[list[str]], asyncio.Task],
        running_flag: asyncio.Event,
    ) -> None:
        """
        Main scheduling loop — calls on_due() with due devices periodically.

        Args:
            on_due: Async callback receiving list of due device IDs.
            running_flag: asyncio.Event signaling when to stop.
        """
        while running_flag.is_set():
            try:
                due = await self.get_due_devices()
                if due:
                    log.debug("scheduler.devices_due", count=len(due))
                    await on_due(due)
            except Exception as exc:
                log.error("scheduler.loop_error", error=str(exc))

            await asyncio.sleep(self._check_interval)

    def get_schedule_summary(self) -> dict[str, int]:
        """Return scheduling stats."""
        now = datetime.now(timezone.utc)
        due_count = sum(1 for t in self._devices.values() if t <= now)
        return {
            "total_devices": len(self._devices),
            "due_for_poll": due_count,
            "scheduled": len(self._devices) - due_count,
        }
