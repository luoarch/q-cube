"""Spec tests for FakeScheduler (MF-RUNTIME-01A S1)."""

from __future__ import annotations

import pytest

from q3_quant_engine.pilot.scheduler import FakeScheduler


class TestFakeScheduler:
    def test_register_handler(self) -> None:
        sched = FakeScheduler()
        handler = lambda: None
        sched.register("snapshot", "0 18 * * 1-5", handler)
        assert "snapshot" in sched.registered
        assert sched.registered["snapshot"]["handler"] is handler
        assert sched.registered["snapshot"]["schedule"] == "0 18 * * 1-5"

    def test_fire_handler(self) -> None:
        calls: list[str] = []
        sched = FakeScheduler()
        sched.register("snapshot", "daily", lambda: calls.append("fired"))
        sched.fire("snapshot")
        assert calls == ["fired"]

    def test_fire_multiple_times(self) -> None:
        calls: list[int] = []
        sched = FakeScheduler()
        sched.register("job", "daily", lambda: calls.append(len(calls)))
        sched.fire("job")
        sched.fire("job")
        sched.fire("job")
        assert calls == [0, 1, 2]

    def test_fire_unregistered_raises(self) -> None:
        sched = FakeScheduler()
        with pytest.raises(KeyError):
            sched.fire("nonexistent")

    def test_register_multiple_jobs(self) -> None:
        sched = FakeScheduler()
        sched.register("a", "daily", lambda: None)
        sched.register("b", "weekly", lambda: None)
        assert len(sched.registered) == 2

    def test_fire_count(self) -> None:
        sched = FakeScheduler()
        sched.register("job", "daily", lambda: None)
        sched.fire("job")
        sched.fire("job")
        assert sched.fire_count("job") == 2

    def test_fire_count_unregistered(self) -> None:
        sched = FakeScheduler()
        assert sched.fire_count("nope") == 0
