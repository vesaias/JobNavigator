"""R4-T6 coverage · backend/seed.py — the seed/migration helpers run_seeds() calls.

These pin CURRENT behaviour, including the parts that only half-work under
SQLite: `run_migrations()` issues Postgres DDL, so the fixture DB reports most of
the list as failed. That is the real behaviour of the function on this dialect
and is asserted as such — the dialect-neutral statements in the same list are
asserted to have actually run, which is what keeps the "everything failed" case
from hiding a regression.
"""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text

import backend.seed as seed
from backend.models.db import (
    Application, Company, Persona, Resume, Search, Setting, VisaCache,
)
from backend.tests.r4_support import make_job


@pytest.fixture(autouse=True)
def _restore_dedup_cache():
    """`migrate_dedup_tracking_params` can eagerly reload the dedup cache — undo it."""
    import backend.scraper._shared.dedup as dedup
    saved = dedup._tracking_params_cache
    yield
    dedup._tracking_params_cache = saved


def _app(db, status="applied", transitions=None):
    job = make_job(db)
    a = Application(job_id=job.id, status=status, status_transitions=transitions)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ══ _int_setting_keys ═══════════════════════════════════════════════════════


def test_a_non_string_default_is_skipped_by_the_int_key_scan(monkeypatch):
    """The int-guard derives its key set from DEFAULT_SETTINGS and ignores non-str defaults."""
    monkeypatch.setitem(seed.DEFAULT_SETTINGS, "cov_int_default", (17, "an int, not a string"))
    monkeypatch.setitem(seed.DEFAULT_SETTINGS, "cov_none_default", (None, "no default at all"))

    keys = seed._int_setting_keys()
    assert "cov_int_default" not in keys
    assert "cov_none_default" not in keys
    # …while a genuine numeric string default is still picked up automatically.
    assert "scrape_interval_minutes" in keys


# ══ run_migration_statements ════════════════════════════════════════════════


def test_a_non_string_statement_is_skipped_without_abandoning_the_list(test_db):
    """A non-string entry fails, is reported, and everything after it still runs.

    The warning formatter used to call `sql.split()` on the raw entry, so the
    AttributeError escaped its own except block and the rest of the migration list
    was silently dropped — the exact failure the per-statement savepoint loop exists
    to prevent. `str(sql)` in the formatter keeps the skip graceful (R4-E2E-03).
    """
    stmts = ["CREATE TABLE cov_mig_ok (id INTEGER)", 12345, "INSERT INTO cov_mig_ok VALUES (3)"]
    assert seed.run_migration_statements(test_db, stmts) == [12345]

    # The statement before the bad entry ran, and so did the one after it.
    assert test_db.execute(text("SELECT count(*) FROM cov_mig_ok")).scalar() == 1


def test_the_failed_list_preserves_order_and_the_exact_statements(test_db):
    """Every failing statement is returned verbatim, in list order."""
    stmts = [
        "CREATE TABLE cov_mig_two (id INTEGER)",
        "SELECT nope_one(1)",
        "INSERT INTO cov_mig_two VALUES (1)",
        "SELECT nope_two(2)",
    ]
    assert seed.run_migration_statements(test_db, stmts) == ["SELECT nope_one(1)", "SELECT nope_two(2)"]


def test_a_failure_after_a_success_does_not_roll_the_success_back(test_db):
    """Savepoint isolation: the committed row from statement 1 survives statement 2 failing."""
    seed.run_migration_statements(test_db, [
        "CREATE TABLE cov_mig_iso (id INTEGER)",
        "INSERT INTO cov_mig_iso VALUES (11)",
        "INSERT INTO cov_mig_iso VALUES (nonexistent_fn())",
        "INSERT INTO cov_mig_iso VALUES (22)",
    ])
    rows = [r[0] for r in test_db.execute(text("SELECT id FROM cov_mig_iso ORDER BY id"))]
    assert rows == [11, 22]


def test_a_skipped_statement_is_logged_as_a_warning(test_db, caplog):
    """Each failure logs one truncated warning naming the statement."""
    with caplog.at_level("WARNING", logger="jobnavigator.seed"):
        seed.run_migration_statements(test_db, ["SELECT definitely_not_a_function(1)"])
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("Migration skipped" in m and "definitely_not_a_function" in m for m in warnings)


# ══ run_migrations ══════════════════════════════════════════════════════════


def test_run_migrations_runs_the_dialect_neutral_statements(test_db):
    """Under SQLite most of the Postgres DDL is skipped, but the plain UPDATEs still run."""
    screening = _app(test_db, status="screening")
    phone = _app(test_db, status="phone_screen")
    final = _app(test_db, status="final_round")
    untouched = _app(test_db, status="offer")

    seed.run_migrations(test_db)          # must not raise on a non-Postgres dialect

    for a in (screening, phone, final, untouched):
        test_db.refresh(a)
    assert screening.status == "applied"
    assert phone.status == "interview"
    assert final.status == "interview"
    assert untouched.status == "offer"


def test_run_migrations_also_rewrites_retired_transitions(test_db):
    """run_migrations() ends by calling the status_transitions cleanup."""
    a = _app(test_db, status="applied", transitions=[
        {"from": "new", "to": "screening", "at": "t1"},
    ])
    seed.run_migrations(test_db)
    test_db.refresh(a)
    assert a.status_transitions == [{"from": "new", "to": "applied", "at": "t1"}]


# ══ _rewrite_retired_status_transitions ═════════════════════════════════════


def test_retired_statuses_are_remapped_in_place(test_db):
    """screening→applied, phone_screen/final_round→interview; other keys survive."""
    a = _app(test_db, transitions=[
        {"from": "new", "to": "screening", "at": "t1", "source": "manual"},
        {"from": "screening", "to": "offer", "at": "t2", "source": "email"},
    ])
    seed._rewrite_retired_status_transitions(test_db)
    test_db.refresh(a)
    assert a.status_transitions == [
        {"from": "new", "to": "applied", "at": "t1", "source": "manual"},
        {"from": "applied", "to": "offer", "at": "t2", "source": "email"},
    ]


def test_self_transitions_created_by_the_remap_are_dropped(test_db):
    """applied→screening becomes applied→applied and is removed entirely."""
    a = _app(test_db, transitions=[
        {"from": "applied", "to": "screening", "at": "t1"},
        {"from": "screening", "to": "offer", "at": "t2"},
    ])
    seed._rewrite_retired_status_transitions(test_db)
    test_db.refresh(a)
    assert a.status_transitions == [{"from": "applied", "to": "offer", "at": "t2"}]


def test_consecutive_entries_reaching_the_same_target_are_collapsed(test_db):
    """phone_screen and final_round both map to interview — only the first is kept."""
    a = _app(test_db, transitions=[
        {"from": "applied", "to": "phone_screen", "at": "t1"},
        {"from": "phone_screen", "to": "final_round", "at": "t2"},
        {"from": "final_round", "to": "offer", "at": "t3"},
    ])
    seed._rewrite_retired_status_transitions(test_db)
    test_db.refresh(a)
    assert a.status_transitions == [
        {"from": "applied", "to": "interview", "at": "t1"},
        {"from": "interview", "to": "offer", "at": "t3"},
    ]


def test_two_survivors_landing_on_the_same_target_collapse_to_one(test_db):
    """phone_screen and final_round both remap to interview from *different* sources,
    so neither is a self-transition — the collapse pass is what removes the second."""
    a = _app(test_db, transitions=[
        {"from": "applied", "to": "phone_screen", "at": "t1"},
        {"from": "screening", "to": "final_round", "at": "t2"},
        {"from": "final_round", "to": "offer", "at": "t3"},
    ])
    seed._rewrite_retired_status_transitions(test_db)
    test_db.refresh(a)
    assert a.status_transitions == [
        {"from": "applied", "to": "interview", "at": "t1"},
        {"from": "interview", "to": "offer", "at": "t3"},
    ]


def test_a_clean_history_is_left_untouched(test_db):
    """No retired status anywhere → the row is skipped before any rewriting."""
    original = [{"from": "applied", "to": "interview", "at": "t1"},
                {"from": "interview", "to": "rejected", "at": "t2"}]
    a = _app(test_db, transitions=list(original))
    seed._rewrite_retired_status_transitions(test_db)
    test_db.refresh(a)
    assert a.status_transitions == original


@pytest.mark.parametrize("transitions", [None, []])
def test_null_and_empty_histories_are_safe(test_db, transitions):
    """A missing or empty transitions list is a no-op, not a crash."""
    a = _app(test_db, transitions=transitions)
    seed._rewrite_retired_status_transitions(test_db)
    test_db.refresh(a)
    assert a.status_transitions in (None, [])


def test_the_applications_own_status_is_not_touched_by_the_rewrite(test_db):
    """The cleanup rewrites history only; the retired *current* status is the
    separate UPDATE in the migration list, so calling it alone leaves it as-is."""
    a = _app(test_db, status="phone_screen",
             transitions=[{"from": "applied", "to": "phone_screen", "at": "t1"}])
    seed._rewrite_retired_status_transitions(test_db)
    test_db.refresh(a)
    assert a.status == "phone_screen"                      # unchanged
    assert a.status_transitions == [{"from": "applied", "to": "interview", "at": "t1"}]


def test_the_rewrite_logs_only_when_something_changed(test_db, caplog):
    """A no-op pass must not claim it rewrote anything."""
    _app(test_db, transitions=[{"from": "applied", "to": "offer", "at": "t1"}])
    with caplog.at_level("INFO", logger="jobnavigator.seed"):
        seed._rewrite_retired_status_transitions(test_db)
    assert not [r for r in caplog.records if "Status-transition cleanup" in r.getMessage()]

    _app(test_db, transitions=[{"from": "applied", "to": "screening", "at": "t1"}])
    with caplog.at_level("INFO", logger="jobnavigator.seed"):
        seed._rewrite_retired_status_transitions(test_db)
    assert [r for r in caplog.records if "Status-transition cleanup" in r.getMessage()]


# ══ seed_companies ══════════════════════════════════════════════════════════


def test_seed_companies_fills_an_empty_table_once(test_db):
    """Seed companies land inactive with playwright on; a second run is a no-op."""
    seed.seed_companies(test_db)
    names = {c.name for c in test_db.query(Company).all()}
    assert names == {c["name"] for c in seed.SEED_COMPANIES}

    cf = test_db.query(Company).filter(Company.name == "Cloudflare").one()
    assert cf.active is False and cf.playwright_enabled is True
    assert cf.scrape_urls == ["https://boards.greenhouse.io/cloudflare"]

    seed.seed_companies(test_db)
    assert test_db.query(Company).count() == len(seed.SEED_COMPANIES)


def test_seed_companies_bails_when_any_company_exists(test_db):
    """One user-added company is enough to suppress the whole seed list."""
    test_db.add(Company(name="MyOwnCo"))
    test_db.commit()
    seed.seed_companies(test_db)
    assert [c.name for c in test_db.query(Company).all()] == ["MyOwnCo"]


# ══ seed_h1b_slugs ══════════════════════════════════════════════════════════


def test_seed_h1b_slugs_is_a_no_op_with_no_overrides(test_db):
    """The shipped override map is empty, so the migration touches nothing."""
    assert seed.H1B_SLUG_OVERRIDES == {}
    test_db.add(Company(name="Acme"))
    test_db.commit()
    seed.seed_h1b_slugs(test_db)
    assert test_db.query(Company).filter(Company.name == "Acme").one().h1b_slug is None


def test_seed_h1b_slugs_fills_only_empty_slugs_of_known_companies(test_db, monkeypatch):
    """An override applies to a matching company with no slug; it never overwrites one."""
    monkeypatch.setattr(seed, "H1B_SLUG_OVERRIDES",
                        {"Acme": "acme-corporation", "Beta": "beta-inc", "Ghost": "ghost-co"})
    test_db.add(Company(name="Acme"))
    test_db.add(Company(name="Beta", h1b_slug="already-set"))
    test_db.commit()

    seed.seed_h1b_slugs(test_db)

    assert test_db.query(Company).filter(Company.name == "Acme").one().h1b_slug == "acme-corporation"
    assert test_db.query(Company).filter(Company.name == "Beta").one().h1b_slug == "already-set"
    assert test_db.query(Company).filter(Company.name == "Ghost").first() is None


# ══ cleanup_removed_settings ════════════════════════════════════════════════


def test_removed_settings_are_deleted_and_live_ones_kept(test_db):
    """Every retired key is dropped; anything still in DEFAULT_SETTINGS stays."""
    for key in ("followup_reminder_days", "h1b_exclusion_phrases", "language_exclude_phrases",
                "default_cv_id", "max_jobs_per_scrape", "company_domains", "ats_domains",
                "autofill_decline_self_id", "llm_base_url", "llm_fallback_base_url",
                "autofill_structured_enabled", "autofill_structured_trigger"):
        test_db.add(Setting(key=key, value="x"))
    test_db.add(Setting(key="fit_score_threshold", value="60"))
    test_db.commit()

    seed.cleanup_removed_settings(test_db)

    assert {s.key for s in test_db.query(Setting).all()} == {"fit_score_threshold"}
    # …and none of the deleted keys is one PATCH /api/settings would still accept.
    assert not seed.is_known_setting("llm_base_url")


def test_cleanup_removed_settings_on_a_clean_db_is_a_no_op(test_db):
    seed.cleanup_removed_settings(test_db)
    assert test_db.query(Setting).count() == 0


# ══ migrate_cv_terminology ══════════════════════════════════════════════════


def test_cv_wording_is_renamed_but_template_tokens_survive(test_db):
    """Word-boundary rename: "CV"/"CVs" become Resume/Resumes, CV_NAMES_HERE does not."""
    test_db.add(Setting(key="scoring_rubric",
                        value="Score each CV. Compare CVs. Emit CV_NAMES_HERE and CVX."))
    test_db.commit()

    seed.migrate_cv_terminology(test_db)

    assert test_db.query(Setting).one().value == \
        "Score each Resume. Compare Resumes. Emit CV_NAMES_HERE and CVX."


def test_cv_wording_migration_is_idempotent_and_tolerates_gaps(test_db):
    """A missing row, an empty value and an already-migrated value are all no-ops."""
    seed.migrate_cv_terminology(test_db)              # no row at all
    test_db.add(Setting(key="scoring_rubric", value=""))
    test_db.commit()
    seed.migrate_cv_terminology(test_db)              # empty value
    assert test_db.query(Setting).one().value == ""

    row = test_db.query(Setting).one()
    row.value = "Score each Resume."
    test_db.commit()
    seed.migrate_cv_terminology(test_db)
    assert test_db.query(Setting).one().value == "Score each Resume."


# ══ migrate_llm_settings — malformed JSON paths ═════════════════════════════


def test_an_unparseable_model_list_is_rebuilt_from_the_defaults(test_db):
    """Corrupt `llm_models_list` JSON is treated as empty, not fatal."""
    test_db.add(Setting(key="llm_models_list", value="{not json at all"))
    test_db.commit()

    seed.migrate_llm_settings(test_db)

    result = json.loads(test_db.query(Setting).filter(Setting.key == "llm_models_list").one().value)
    assert result == json.loads(seed.DEFAULT_SETTINGS["llm_models_list"][0])


def test_an_unparseable_seen_marker_is_treated_as_empty(test_db):
    """Corrupt `llm_seeded_models` JSON means "nothing offered yet" — defaults re-seed."""
    test_db.add(Setting(key="llm_models_list", value=json.dumps(
        [{"provider": "ollama", "model": "mine"}])))
    test_db.add(Setting(key="llm_seeded_models", value="<<<broken>>>"))
    test_db.commit()

    seed.migrate_llm_settings(test_db)

    models = json.loads(test_db.query(Setting).filter(Setting.key == "llm_models_list").one().value)
    assert {"provider": "ollama", "model": "mine"} in models
    assert {"provider": "claude_api", "model": "claude-sonnet-5"} in models
    seen = json.loads(test_db.query(Setting).filter(Setting.key == "llm_seeded_models").one().value)
    assert "claude_api|claude-sonnet-5" in seen
    assert seen == sorted(seen)


# ══ seed_searches ═══════════════════════════════════════════════════════════


def test_seed_searches_seeds_one_per_mode(test_db):
    """Every shipped search mode gets a row; a second call adds nothing."""
    seed.seed_searches(test_db)
    modes = [s.search_mode for s in test_db.query(Search).all()]
    assert sorted(modes) == sorted(s["search_mode"] for s in seed.SEED_SEARCHES)

    ext = test_db.query(Search).filter(Search.search_mode == "extension").one()
    assert ext.active is True and ext.auto_scoring_depth == "light"

    seed.seed_searches(test_db)
    assert test_db.query(Search).count() == len(seed.SEED_SEARCHES)


def test_seed_searches_renames_the_legacy_extension_search(test_db):
    """A pre-existing "LinkedIn Extension" row is renamed in place, not duplicated."""
    test_db.add(Search(name="LinkedIn Extension", search_mode="linkedin_extension"))
    test_db.commit()

    seed.seed_searches(test_db)

    rows = test_db.query(Search).filter(Search.search_mode == "linkedin_extension").all()
    assert len(rows) == 1
    assert rows[0].name == "Extension LI"


def test_a_user_renamed_search_of_a_seeded_mode_blocks_the_seed(test_db):
    """Mode — not name — is the identity, so an existing mode is never re-seeded."""
    test_db.add(Search(name="My Own Keywords", search_mode="keyword"))
    test_db.commit()
    seed.seed_searches(test_db)
    assert [s.name for s in test_db.query(Search).filter(Search.search_mode == "keyword").all()] \
        == ["My Own Keywords"]


# ══ seed_mock_resume ════════════════════════════════════════════════════════


def test_mock_resume_is_seeded_and_wired_up(test_db):
    """The sample base resume becomes default_resume_id and every company's selection."""
    test_db.add(Setting(key="default_resume_id", value=""))
    test_db.add(Company(name="Acme"))
    test_db.add(Company(name="Beta"))
    test_db.commit()

    seed.seed_mock_resume(test_db)

    resume = test_db.query(Resume).one()
    assert resume.name == "Sample PM" and resume.is_base is True
    assert resume.template == "garamond_alt" and resume.page_format == "letter"
    assert resume.json_data["header"]["name"] == "Alex Johnson"
    assert test_db.query(Setting).filter(Setting.key == "default_resume_id").one().value == str(resume.id)
    for c in test_db.query(Company).all():
        assert c.selected_resume_ids == [str(resume.id)]


def test_mock_resume_is_skipped_when_a_base_resume_exists(test_db):
    """A user with their own base résumé never gets the sample."""
    test_db.add(Resume(name="Mine", is_base=True, json_data={}))
    test_db.commit()
    seed.seed_mock_resume(test_db)
    assert [r.name for r in test_db.query(Resume).all()] == ["Mine"]


def test_mock_resume_seeds_even_without_a_default_resume_setting(test_db):
    """No `default_resume_id` row yet → the resume is still created, nothing crashes."""
    seed.seed_mock_resume(test_db)
    assert test_db.query(Resume).filter(Resume.name == "Sample PM").count() == 1
    assert test_db.query(Setting).filter(Setting.key == "default_resume_id").first() is None


def test_a_tailored_copy_does_not_count_as_a_base_resume(test_db):
    """`is_base = False` copies do not suppress the seed."""
    test_db.add(Resume(name="Tailored", is_base=False, json_data={}))
    test_db.commit()
    seed.seed_mock_resume(test_db)
    assert test_db.query(Resume).filter(Resume.name == "Sample PM").count() == 1


# ══ seed_persona ════════════════════════════════════════════════════════════


def test_persona_singleton_is_created_once(test_db):
    seed.seed_persona(test_db)
    p = test_db.query(Persona).one()
    assert p.id == 1 and p.contact == {} and p.qa_bank == []

    p.contact = {"name": "V"}
    test_db.commit()
    seed.seed_persona(test_db)                     # must not clobber the user's data
    assert test_db.query(Persona).one().contact == {"name": "V"}


# ══ migrate_h1b_to_visa_cache ═══════════════════════════════════════════════


LEGACY_COLS = [("h1b_lca_count", "INTEGER"), ("h1b_approval_rate", "FLOAT"),
               ("h1b_median_salary", "INTEGER"), ("h1b_last_checked", "DATETIME")]


def _add_legacy_columns(db):
    for col, typ in LEGACY_COLS:
        db.execute(text(f"ALTER TABLE companies ADD COLUMN {col} {typ}"))
    db.commit()


def _fake_dialect(monkeypatch, db, name):
    """Make the migration's one `db.get_bind()` probe report `name`.

    Only that first bare call is faked — every later ORM call (which passes a
    mapper/clause) still gets the real bind, so queries keep working.
    """
    original = db.get_bind
    state = {"used": False}

    def _get_bind(*a, **k):
        if not state["used"] and not a and not k:
            state["used"] = True
            return SimpleNamespace(dialect=SimpleNamespace(name=name))
        return original(*a, **k)

    monkeypatch.setattr(db, "get_bind", _get_bind, raising=False)


def test_an_unknown_dialect_returns_immediately(test_db, monkeypatch):
    """Neither Postgres nor SQLite → the migration does nothing at all."""
    _fake_dialect(monkeypatch, test_db, "mysql")

    def _boom(*a, **k):
        raise AssertionError("no SQL may be issued on an unknown dialect")
    monkeypatch.setattr(test_db, "execute", _boom, raising=False)

    seed.migrate_h1b_to_visa_cache(test_db)        # returns without touching the DB


def test_a_column_probe_failure_returns_quietly(test_db, monkeypatch):
    """If the column probe raises, the migration gives up rather than propagating."""
    original = test_db.execute

    def _fail_pragma(stmt, *a, **k):
        if "PRAGMA" in str(stmt):
            raise RuntimeError("probe exploded")
        return original(stmt, *a, **k)
    monkeypatch.setattr(test_db, "execute", _fail_pragma, raising=False)

    seed.migrate_h1b_to_visa_cache(test_db)
    assert test_db.query(VisaCache).count() == 0


def test_a_postgres_db_without_the_legacy_column_is_already_migrated(test_db, monkeypatch):
    """The Postgres probe uses information_schema; no h1b_lca_count → early return."""
    _fake_dialect(monkeypatch, test_db, "postgresql")
    original = test_db.execute
    seen = []

    def _fake(stmt, *a, **k):
        s = str(stmt)
        seen.append(s)
        if "information_schema" in s:
            return [("id",), ("name",), ("h1b_slug",)]
        return original(stmt, *a, **k)
    monkeypatch.setattr(test_db, "execute", _fake, raising=False)

    seed.migrate_h1b_to_visa_cache(test_db)

    assert any("information_schema" in s for s in seen)
    assert not any("select name, h1b_slug" in s for s in seen)
    assert test_db.query(VisaCache).count() == 0


def test_a_failing_legacy_select_seeds_nothing(test_db, monkeypatch):
    """A broken read of the legacy columns degrades to "no rows", not an exception."""
    _add_legacy_columns(test_db)
    original = test_db.execute

    def _fail_select(stmt, *a, **k):
        if "select name, h1b_slug" in str(stmt):
            raise RuntimeError("select exploded")
        return original(stmt, *a, **k)
    monkeypatch.setattr(test_db, "execute", _fail_select, raising=False)

    seed.migrate_h1b_to_visa_cache(test_db)
    assert test_db.query(VisaCache).count() == 0


def test_only_companies_with_data_or_a_slug_are_copied(test_db):
    """Blank names, names already in visa_cache and dataless rows are all skipped."""
    _add_legacy_columns(test_db)
    test_db.add_all([
        Company(name="   "),                       # blank key → skipped
        Company(name="DupCo"),                     # already in visa_cache → skipped
        Company(name="EmptyCo"),                   # no data, no slug → skipped
        Company(name="SlugOnlyCo", h1b_slug="slug-only"),
        Company(name="DataCo"),
    ])
    test_db.add(VisaCache(name_key="dupco", country="US", display_name="Existing"))
    test_db.commit()
    test_db.execute(text("update companies set h1b_lca_count=320, h1b_approval_rate=92.0, "
                         "h1b_median_salary=165000 where name='DataCo'"))
    test_db.execute(text("update companies set h1b_lca_count=99 where name='DupCo'"))
    test_db.commit()

    seed.migrate_h1b_to_visa_cache(test_db)

    keys = {v.name_key for v in test_db.query(VisaCache).all()}
    assert keys == {"dupco", "slugonlyco", "dataco"}
    assert test_db.query(VisaCache).filter(VisaCache.name_key == "dupco").one().display_name == "Existing"

    data = test_db.query(VisaCache).filter(VisaCache.name_key == "dataco").one()
    assert data.lca_count == 320 and data.median_salary == 165000 and data.has_data is True

    slug_only = test_db.query(VisaCache).filter(VisaCache.name_key == "slugonlyco").one()
    assert slug_only.slug == "slug-only" and slug_only.has_data is False


def test_postgres_drops_the_legacy_columns_and_survives_one_failing_drop(test_db, monkeypatch, caplog):
    """All four DROP COLUMN statements are attempted; one failing is only logged."""
    _add_legacy_columns(test_db)
    test_db.add(Company(name="DataCo", h1b_slug="data-co"))
    test_db.commit()
    _fake_dialect(monkeypatch, test_db, "postgresql")

    original = test_db.execute
    dropped = []

    def _fake(stmt, *a, **k):
        s = str(stmt)
        if "information_schema" in s:
            return [("name",), ("h1b_lca_count",)]
        if "DROP COLUMN IF EXISTS" in s:
            col = s.rsplit(" ", 1)[-1]
            dropped.append(col)
            if col == "h1b_median_salary":
                raise RuntimeError("cannot drop, view depends on it")
            return None
        return original(stmt, *a, **k)
    monkeypatch.setattr(test_db, "execute", _fake, raising=False)

    with caplog.at_level("WARNING", logger="jobnavigator.seed"):
        seed.migrate_h1b_to_visa_cache(test_db)

    assert dropped == ["h1b_lca_count", "h1b_approval_rate",
                       "h1b_median_salary", "h1b_last_checked"]
    assert any("drop legacy column h1b_median_salary failed" in r.getMessage()
               for r in caplog.records)
    assert test_db.query(VisaCache).filter(VisaCache.name_key == "dataco").count() == 1


def test_sqlite_keeps_the_legacy_columns(test_db):
    """The DROP half is Postgres-only; on SQLite the columns are left in place."""
    _add_legacy_columns(test_db)
    test_db.add(Company(name="DataCo", h1b_slug="data-co"))
    test_db.commit()

    seed.migrate_h1b_to_visa_cache(test_db)

    cols = {r[1] for r in test_db.execute(text("PRAGMA table_info(companies)"))}
    assert "h1b_lca_count" in cols
    # …and re-running is therefore not idempotent-by-column, but is by name_key.
    seed.migrate_h1b_to_visa_cache(test_db)
    assert test_db.query(VisaCache).filter(VisaCache.name_key == "dataco").count() == 1


def test_a_fresh_install_without_the_legacy_columns_is_a_no_op(test_db):
    """The shipped Company model has no h1b_lca_count, so this is the normal path."""
    test_db.add(Company(name="Acme"))
    test_db.commit()
    seed.migrate_h1b_to_visa_cache(test_db)
    assert test_db.query(VisaCache).count() == 0


# ══ migrate_autofill_dicts ══════════════════════════════════════════════════


def test_autofill_dicts_gain_missing_defaults_without_losing_edits(test_db):
    """Only absent top-level keys are added; the user's own values are preserved."""
    test_db.add(Setting(key="autofill_field_patterns",
                        value=json.dumps({"veteran_status": ["my own pattern"],
                                          "my_custom_field": ["mine"]})))
    test_db.add(Setting(key="autofill_option_synonyms", value=json.dumps({})))
    test_db.commit()

    seed.migrate_autofill_dicts(test_db)

    patterns = json.loads(test_db.query(Setting)
                          .filter(Setting.key == "autofill_field_patterns").one().value)
    assert patterns["veteran_status"] == ["my own pattern"]      # edit kept
    assert patterns["my_custom_field"] == ["mine"]               # custom key kept
    defaults = json.loads(seed.DEFAULT_SETTINGS["autofill_field_patterns"][0])
    assert set(defaults) <= set(patterns)                        # every default present

    syn = json.loads(test_db.query(Setting)
                     .filter(Setting.key == "autofill_option_synonyms").one().value)
    assert syn == json.loads(seed.DEFAULT_SETTINGS["autofill_option_synonyms"][0])


def test_autofill_dicts_migration_skips_missing_and_broken_rows(test_db):
    """No row → nothing to merge; unparseable JSON is left exactly as the user left it."""
    seed.migrate_autofill_dicts(test_db)                          # no rows at all
    assert test_db.query(Setting).count() == 0

    test_db.add(Setting(key="autofill_field_patterns", value="{ broken"))
    test_db.commit()
    seed.migrate_autofill_dicts(test_db)
    assert test_db.query(Setting).one().value == "{ broken"


def test_autofill_dicts_migration_is_idempotent(test_db):
    """A row already carrying every default is not rewritten."""
    default = seed.DEFAULT_SETTINGS["autofill_field_patterns"][0]
    test_db.add(Setting(key="autofill_field_patterns", value=default))
    test_db.commit()
    seed.migrate_autofill_dicts(test_db)
    assert test_db.query(Setting).one().value == default


# ══ migrate_dedup_tracking_params ═══════════════════════════════════════════


def test_a_non_list_dedup_setting_is_left_alone(test_db):
    """Valid JSON of the wrong shape is not rewritten."""
    test_db.add(Setting(key="dedup_tracking_params", value=json.dumps({"jk": True})))
    test_db.commit()
    seed.migrate_dedup_tracking_params(test_db)
    assert json.loads(test_db.query(Setting).one().value) == {"jk": True}


def test_a_failing_eager_reload_does_not_break_the_migration(test_db, monkeypatch):
    """The cache reloads lazily anyway, so a reload failure is swallowed after the write."""
    import backend.scraper._shared.dedup as dedup

    def _explode():
        raise RuntimeError("cache reload failed")
    monkeypatch.setattr(dedup, "reload_tracking_params", _explode)

    test_db.add(Setting(key="dedup_tracking_params", value=json.dumps(["jk", "utm_source"])))
    test_db.commit()

    seed.migrate_dedup_tracking_params(test_db)          # must not raise
    assert json.loads(test_db.query(Setting).one().value) == ["utm_source"]


# ══ run_seeds ═══════════════════════════════════════════════════════════════


def test_run_seeds_brings_an_empty_database_up(test_db):
    """The whole startup path in order: migrations, settings, companies, searches,
    the sample résumé, the persona and the cleanup/upgrade migrations."""
    seed.run_seeds()

    settings = {s.key: s.value for s in test_db.query(Setting).all()}
    for key in seed.DEFAULT_SETTINGS:
        assert key in settings, f"{key} was not seeded"
    # The one-shot secret is generated, not left at its seeded empty value.
    assert len(settings["telegram_webhook_secret"]) >= 32

    assert test_db.query(Company).count() == len(seed.SEED_COMPANIES)
    assert {s.search_mode for s in test_db.query(Search).all()} == \
        {s["search_mode"] for s in seed.SEED_SEARCHES}
    assert test_db.query(Resume).filter(Resume.name == "Sample PM").count() == 1
    assert test_db.query(Persona).filter(Persona.id == 1).count() == 1
    # migrate_llm_settings ran: the seen-marker exists and the list is real JSON.
    assert json.loads(settings["llm_seeded_models"])
    assert json.loads(settings["llm_models_list"])


def test_run_seeds_is_idempotent(test_db):
    """A second boot changes nothing that matters."""
    seed.run_seeds()
    secret = test_db.query(Setting).filter(
        Setting.key == "telegram_webhook_secret").one().value
    resume_id = test_db.query(Resume).filter(Resume.name == "Sample PM").one().id

    seed.run_seeds()

    assert test_db.query(Setting).filter(
        Setting.key == "telegram_webhook_secret").one().value == secret
    assert test_db.query(Resume).filter(Resume.name == "Sample PM").one().id == resume_id
    assert test_db.query(Company).count() == len(seed.SEED_COMPANIES)
    assert test_db.query(Search).count() == len(seed.SEED_SEARCHES)
    assert test_db.query(Persona).count() == 1
