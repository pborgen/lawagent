"""Login + session persistence for CT eServices.

First run: opens a Chromium window, fills the login form, saves
`storage_state.json`. Later runs reuse that file silently.

If the session expires, delete the storage state file (path is in
EFILE_STORAGE_STATE) and re-run.

NOTE: the selectors below are TODO placeholders. Open the eServices
login page in your browser, dev-tools the username and password
inputs, and fill in their actual `name` / `id` / CSS selectors.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from efile.src.throttle import polite_wait


# ─── TODO: confirm against the live page ─────────────────────────────
# Open https://efile.eservices.jud.ct.gov in dev-tools and copy the
# real selectors. ASP.NET often uses names like "ctl00$..." which need
# to be quoted exactly.
LOGIN_URL = "https://eservices.jud.ct.gov/Login.aspx"  # TODO confirm
USERNAME_SELECTOR = "#ctl00_cphBody_txtUserID"
PASSWORD_SELECTOR = "#ctl00_cphBody_txtPassword"
SUBMIT_SELECTOR = "#ctl00_cphBody_btnLogin"
# A selector that only exists when logged in — used to verify success.
LOGGED_IN_MARKER = "#ctl00_hlnkLogOut"
# ─────────────────────────────────────────────────────────────────────


def _storage_state_path() -> Path:
    return Path(
        os.getenv(
            "EFILE_STORAGE_STATE",
            "./data/case/efile/.storage_state.json",
        )
    )


def _credentials() -> tuple[str, str]:
    user = os.getenv("EFILE_USERNAME") or ""
    pwd = os.getenv("EFILE_PASSWORD") or ""
    if not user or not pwd:
        raise RuntimeError(
            "EFILE_USERNAME and EFILE_PASSWORD must be set in your .env."
        )
    return user, pwd


def _do_login(page: Page) -> None:
    user, pwd = _credentials()

    page.goto(LOGIN_URL, wait_until="networkidle")
    polite_wait("after login page load")

    page.fill(USERNAME_SELECTOR, user)
    page.fill(PASSWORD_SELECTOR, pwd)
    polite_wait("before submit")

    page.click(SUBMIT_SELECTOR)
    page.wait_for_load_state("networkidle")
    polite_wait("after submit")

    # Verify login succeeded.
    if page.locator(LOGGED_IN_MARKER).count() == 0:
        raise RuntimeError(
            "Login appears to have failed. Check EFILE_USERNAME / "
            "EFILE_PASSWORD, then re-check the LOGIN_URL and "
            "*_SELECTOR constants in apps/efile/src/auth.py against the "
            "live page."
        )


@contextmanager
def authenticated_context(
    headless: bool = True,
    force_login: bool = False,
) -> Iterator[tuple[Browser, BrowserContext, Page]]:
    """Yield a Playwright (browser, context, page) that is logged in.

    Reuses a saved storage_state if present; otherwise performs a fresh
    login and saves it on the way out.
    """
    storage_path = _storage_state_path()
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    use_existing = storage_path.exists() and not force_login

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        ctx_kwargs: dict = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        if use_existing:
            ctx_kwargs["storage_state"] = str(storage_path)

        context = browser.new_context(**ctx_kwargs)
        # Generous default — many CT pages are slow.
        context.set_default_timeout(45_000)

        page = context.new_page()

        if not use_existing:
            _do_login(page)
            context.storage_state(path=str(storage_path))

        try:
            yield browser, context, page
        finally:
            # Refresh storage_state on the way out (cookies may have rotated).
            try:
                context.storage_state(path=str(storage_path))
            except Exception:
                pass
            context.close()
            browser.close()
