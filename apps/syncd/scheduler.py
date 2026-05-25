"""Shared APScheduler instance used by every job in `syncd/jobs/`.

Job files do not construct their own scheduler — they import `sched` from
here and decorate functions with `@sched.scheduled_job(...)`. That keeps
every job discoverable from one place (the `jobs/` folder) and lets the
daemon start them all with a single `sched.start()`.
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler


sched = BlockingScheduler()
