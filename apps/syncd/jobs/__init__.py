"""Auto-discover every job module in this folder.

Each `.py` file in `apps/syncd/jobs/` is imported on startup so that its
`@sched.scheduled_job(...)` decorators run and register their jobs. To
add a new scheduled job, drop a new file in here — no wiring required.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path


_here = Path(__file__).parent
for _info in pkgutil.iter_modules([str(_here)]):
    if _info.name.startswith("_"):
        continue
    importlib.import_module(f"{__name__}.{_info.name}")
