"""R4-T1 · backup content checks (item 5 of the track).

The restore half of the drill runs against a scratch database inside the db
container (see v2-testing/round4/T1.md for the recorded run); what belongs in the
suite is the part that can be re-checked cheaply and must not regress: a `pg_dump`
snapshot is a secret-bearing artefact, and the dashboard must never hand one out
in clear.

Skips when the baseline dump or `pg_restore` is not available (i.e. outside the
backend container).
"""
import os
import pathlib
import shutil
import subprocess

import pytest

DUMP = pathlib.Path("/app/backups/round4_baseline_20260905.dump")
ENV = pathlib.Path("/app/.env")


def _env_secrets():
    """Long values from the environment that must be treated as secrets."""
    out = {}
    for key in ("ANTHROPIC_API_KEY", "INITIAL_API_KEY", "TELEGRAM_BOT_TOKEN",
                "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        value = os.getenv(key, "")
        if len(value) >= 8:
            out[key] = value
    return out


@pytest.fixture(scope="module")
def settings_sql():
    """The `settings` table rows from the baseline dump, as plain SQL."""
    if not DUMP.exists():
        pytest.skip(f"baseline dump not mounted at {DUMP}")
    if not shutil.which("pg_restore"):
        pytest.skip("pg_restore not available")
    proc = subprocess.run(
        ["pg_restore", "--data-only", "--table=settings", "-f", "-", str(DUMP)],
        capture_output=True, timeout=300,
    )
    if proc.returncode != 0:
        pytest.skip(f"pg_restore failed: {proc.stderr[:200]!r}")
    return proc.stdout.decode("utf-8", "replace")


def test_the_dump_restores_its_settings_table(settings_sql):
    assert "COPY public.settings" in settings_sql
    assert "dashboard_api_key" in settings_sql


def test_the_dump_carries_the_whole_settings_table(settings_sql):
    """A dump missing rows is a silent data-loss bug — count the COPY payload."""
    body = settings_sql.split("COPY public.settings", 1)[1]
    rows = [l for l in body.splitlines()[1:] if l and l != "\\."]
    assert len(rows) >= 50, f"only {len(rows)} settings rows in the dump"


@pytest.mark.xfail(strict=True, reason="R4-T1-29")
def test_the_dump_contains_no_env_secret_in_clear(settings_sql):
    """Backups are secret-bearing: the LLM key and the dashboard key ship in clear.

    `POST /api/db/backup` writes these into /app/backups on a cron, and the
    repository's own `backups/` directory holds them.
    """
    secrets = _env_secrets()
    if not secrets:
        pytest.skip("no long secrets configured in this environment")
    found = [k for k, v in secrets.items() if v in settings_sql]
    assert not found, f"{found} present in the dump's settings table"


def test_which_env_secrets_reach_the_dump_is_recorded(settings_sql):
    """Companion to the xfail above: pins WHICH keys leak, so a partial fix shows up."""
    secrets = _env_secrets()
    if not secrets:
        pytest.skip("no long secrets configured in this environment")
    found = sorted(k for k, v in secrets.items() if v in settings_sql)
    assert found == ["ANTHROPIC_API_KEY", "INITIAL_API_KEY"], found


def test_a_dump_never_reaches_the_api_surface(client):  # noqa: F811
    """No route serves a backup file; /api/db/backup only returns a run id."""
    from backend.main import app
    paths = {r.path for r in app.routes}
    assert not any("backup" in p and "{" in p for p in paths)
    assert "/api/db/backup" in paths


from backend.tests.r4_support import client, _clear_running_state, _no_outbound  # noqa: E402,F401
