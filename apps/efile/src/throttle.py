"""Polite waits to avoid timeouts / rate-limiting on CT eServices.

The CT Judicial Branch portal is not a high-traffic API; hammering
it gets you logged out (and potentially flagged). Every navigation
and download goes through `polite_wait()`.

Tune via env vars:
    EFILE_MIN_WAIT_SECONDS         (default 2)
    EFILE_MAX_WAIT_SECONDS         (default 5)
    EFILE_DOWNLOAD_DELAY_SECONDS   (default 1)
"""
from __future__ import annotations

import os
import random
import time
from typing import Callable, TypeVar


T = TypeVar("T")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def polite_wait(label: str = "") -> None:
    """Sleep a random duration between EFILE_MIN_WAIT_SECONDS and EFILE_MAX_WAIT_SECONDS."""
    lo = _env_float("EFILE_MIN_WAIT_SECONDS", 2.0)
    hi = _env_float("EFILE_MAX_WAIT_SECONDS", 5.0)
    if hi < lo:
        lo, hi = hi, lo
    delay = random.uniform(lo, hi)
    if label:
        # Caller can log this; keeping it as a side-channel via stderr would
        # couple this module to a logger. Just sleep.
        pass
    time.sleep(delay)


def download_delay() -> None:
    """Extra short pause before initiating a file download."""
    delay = _env_float("EFILE_DOWNLOAD_DELAY_SECONDS", 1.0)
    time.sleep(delay)


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_backoff: float = 5.0,
    label: str = "",
) -> T:
    """Run `fn` with exponential backoff on transient failures.

    Designed for "the page didn't load" or "session expired" cases.
    Re-raises the last exception if all attempts fail.
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if i == attempts - 1:
                break
            time.sleep(base_backoff * (2**i))
    assert last_exc is not None
    raise last_exc
