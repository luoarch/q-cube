"""Scheduler abstraction — testable via FakeScheduler.

No cron, no celery beat, no PM2. Just an interface + fake for tests.
"""

from __future__ import annotations

from typing import Callable, Protocol


class JobScheduler(Protocol):
    """Abstract scheduler interface."""

    def register(self, name: str, schedule: str, handler: Callable[[], None]) -> None: ...


class FakeScheduler:
    """Test fake — captures registrations, fires handlers on demand."""

    def __init__(self) -> None:
        self.registered: dict[str, dict] = {}
        self._fire_counts: dict[str, int] = {}

    def register(self, name: str, schedule: str, handler: Callable[[], None]) -> None:
        self.registered[name] = {"schedule": schedule, "handler": handler}
        self._fire_counts.setdefault(name, 0)

    def fire(self, name: str) -> None:
        """Manually trigger a registered handler. Raises KeyError if not registered."""
        entry = self.registered[name]  # raises KeyError if missing
        entry["handler"]()
        self._fire_counts[name] = self._fire_counts.get(name, 0) + 1

    def fire_count(self, name: str) -> int:
        """Return how many times a job has been fired."""
        return self._fire_counts.get(name, 0)
