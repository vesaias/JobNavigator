"""Resolve desired runners from all effective account settings; sync with controller."""
import asyncio
import logging
import os

import httpx

from backend.cli_runner.auth import ensure_token
from backend.cli_runner.protocol import SERVICES

logger = logging.getLogger("jobnavigator.runner_management")
PROVIDER_KEYS = ("llm_provider", "scoring_llm_provider", "llm_fallback_provider",
                 "cv_tailor_llm_provider", "cover_letter_llm_provider",
                 "autofill_llm_provider", "email_llm_provider")


def enabled():
    return os.getenv("JN_RUNNER_MANAGEMENT", "0").lower() in ("1", "true", "yes")


def manager_url():
    return os.getenv("JN_RUNNER_MANAGER_URL", "http://runner-manager:8000").rstrip("/")


def account_providers(db):
    from backend.accounts.settings import get_setting
    return {get_setting(db, key) for key in PROVIDER_KEYS} & SERVICES.keys()


def required_providers():
    from backend.models.db import Account, SessionLocal
    from backend.accounts.context import unscoped
    from backend.accounts.background import acting_as
    with SessionLocal() as db, unscoped():
        accounts = [row[0] for row in db.query(Account.id).all()]
    required = set()
    for account in accounts or [None]:
        with acting_as(account), SessionLocal() as db:
            required.update(account_providers(db))
    return sorted(required)


class Coordinator:
    def __init__(self):
        self.task = None
        self.wake = asyncio.Event()
        self.snapshot = {"providers": []}
        self.error = False
        self.retry_requested = False
        self.loop = None

    def notify(self):
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.wake.set)

    async def sync(self):
        # Settings reads must not block the API event loop while the DB is slow.
        desired = await asyncio.to_thread(required_providers)
        token = ensure_token()
        async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
            response = await client.put(f"{manager_url()}/v1/desired", json={"providers": desired},
                                        headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            if self.retry_requested:
                retry = await client.post(f"{manager_url()}/v1/retry", json={"providers": desired},
                                          headers={"Authorization": f"Bearer {token}"})
                retry.raise_for_status()
                self.retry_requested = False
            state = response.json()
            if state.get("management_version") != 1 or not isinstance(state.get("providers"), list):
                raise ValueError("Incompatible runner manager")
            self.snapshot = state
            self.error = False

    async def run(self):
        while True:
            self.wake.clear()
            try:
                await self.sync()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not self.error:
                    logger.warning("Runner manager synchronization failed (%s)", type(exc).__name__)
                self.error = True
            try:
                await asyncio.wait_for(self.wake.wait(), 3)
            except asyncio.TimeoutError:
                pass

    def start(self):
        from backend.accounts.context import run_in_clean_context
        self.loop = asyncio.get_running_loop()
        self.wake = asyncio.Event()
        self.task = run_in_clean_context(lambda: asyncio.create_task(self.run()))

    async def stop(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
            self.loop = None


coordinator = Coordinator()


def notify():
    if enabled():
        coordinator.notify()
