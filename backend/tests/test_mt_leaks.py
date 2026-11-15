"""MT-3 · Leak harness: every API route, called as account A against account B's data.

Accounts: an owner and a member (see the directions below for which is A). Both get one row of every
account-owned model (plus a JobLocation and a TracerClickEvent, and B gets a running
monitor entry and a search test result in memory). Every text field of B's rows carries
MARKER, so a leak shows up in list endpoints too.

The routes come from `app.routes`, so a route added later is tested automatically. For
each (method, route):
  * path parameters get B's id of the matching model (PARAM_MODELS); an unknown parameter
    fails the case as "unmapped" instead of passing silently;
  * mapped query parameters and id-like body fields get B's ids as well, and dict / model
    bodies also carry plausible write fields, so an unscoped write really writes;
  * the response (body and Location header) must not contain MARKER, nor any B id that
    the request did not send itself;
  * GET routes are also called before B's rows exist: the answer must be the same once
    they do (catches counts, sums and existence leaks that carry no marker);
  * B's rows must be unchanged afterwards (snapshot read with unscoped()); A's rows must
    not point at B's rows through a foreign key nor carry MARKER;
  * no background work may be launched with B's ids (launches and BackgroundTasks are
    recorded, never run; network, LLM, browser and JobSpy are stubbed);
  * a 5xx answer fails the case as inconclusive: an erroring route proves nothing.

Since MT-10 every case runs in both directions through the real auth paths: the owner
calls with a signed `X-Account-Token` (API path) against the member's rows, and the member
calls with the signed `jn_account` cookie issued by POST /api/auth/switch (browser path)
against the owner's rows. In each direction "A" is the caller and "B" the victim.

Routes that leak today are listed in KNOWN_LEAKS and run as xfail(strict=True) with the
batch that fixes them (MT-4 / MT-5 / MT-6): fixing a route turns its case into an XPASS,
which fails the suite until the entry is removed. Install-wide routes live in
mt_leak_allowlist.py.
"""
import inspect
import json
import re
import typing
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from backend.accounts.context import unscoped, use_account
from backend.tests.mt_leak_allowlist import ALLOWLIST
from backend.tests.r4_support import _clear_running_state, _no_outbound, account_token, client  # noqa: F401 (fixtures)

MARKER = "ZZB-LEAK-7Q3X"          # in every text field of B's rows
A_TEXT = "a-own-row"               # A's rows: no marker
WRITE_TEXT = "A-WROTE-THIS"        # what A tries to write onto B's rows
B_TOKEN = "zzbtok7q3x"             # B's tracer token (10 chars)
A_TOKEN = "aaatok0001"


def _job_url(token):
    """A job's posting URL. Marker-free, so a body may send B's URL (dedup-by-URL lookups)."""
    return f"https://board-{token[:3]}.example/job/1"


def _cl_token(token):
    return token[:-1] + "c"

# ── Routes that leak today (worklist for MT-4..6; MT-PLAN.md "Unscoped call sites") ──
# Value: "<batch>: why". Fixing a route makes its case XPASS (strict) -> delete the entry.
KNOWN_LEAKS: dict[tuple[str, str], str] = {}

# Path / query / body parameter name -> the B row whose id it receives.
PARAM_MODELS = {
    "job_id": "job",
    "app_id": "application",
    "application_id": "application",
    "interview_id": "interview",
    "company_id": "company",
    "search_id": "search",
    "run_id": "job_run",
    "batch_id": "job_run",          # a generate batch is a JobRun
    "resume_id": "resume",
    "base_resume_id": "resume",
    "tailored_resume_id": "tailored",
    "cl_id": "cover_letter",
    "cover_letter_id": "cover_letter",
    "token": "tracer_token",
    "link_id": "tracer_link",
    "tracer_link_id": "tracer_link",
    "persona_id": "persona",
}
PLURAL_PARAMS = {"job_ids": "job", "resume_ids": "resume", "company_ids": "company",
                 "search_ids": "search", "app_ids": "application",
                 "selected_resume_ids": "resume"}
# `ids` in a bulk body means the ids of the router's own resource.
PREFIX_RESOURCE = {
    "/api/jobs": "job", "/api/applications": "application", "/api/companies": "company",
    "/api/searches": "search", "/api/resumes": "resume", "/api/cover-letters": "cover_letter",
}
# Fields a dict body carries so an unscoped write on B's row actually changes it.
WRITE_FIELDS = {
    "/api/applications/interviews": {"what": WRITE_TEXT, "prep": WRITE_TEXT, "status": "done"},
    "/api/applications": {"status": "rejected", "notes": WRITE_TEXT},
    "/api/jobs": {"status": "skip", "seen": True, "saved": False},
    "/api/companies": {"notes": WRITE_TEXT, "active": False},
    "/api/searches": {"name": WRITE_TEXT, "active": False},
    "/api/resumes": {"name": WRITE_TEXT},
    "/api/cover-letters": {"name": WRITE_TEXT},
}

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\b[0-9a-f]{32}\b", re.I)
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?")


# ── Route enumeration ────────────────────────────────────────────────────────

def _api_routes():
    from backend.main import app
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                out.append((m, r.path, r))
    return out


def _route_cases():
    cases = []
    for method, path, _ in _api_routes():
        key = (method, path)
        if key in ALLOWLIST:
            continue
        marks = []
        if key in KNOWN_LEAKS:
            marks.append(pytest.mark.xfail(strict=True, reason=KNOWN_LEAKS[key]))
        cases.append(pytest.param(method, path, id=f"{method} {path}", marks=marks))
    return cases


def _prefix_of(path):
    for prefix in sorted(WRITE_FIELDS, key=len, reverse=True):
        if path.startswith(prefix):
            return prefix
    return None


def _resource_of(path):
    for prefix, res in PREFIX_RESOURCE.items():
        if path.startswith(prefix):
            return res
    return None


# ── Seeding ──────────────────────────────────────────────────────────────────

def _ids():
    return {k: uuid.uuid4() for k in (
        "search", "company", "job", "job_new", "application", "interview", "resume", "tailored",
        "cover_letter", "tracer_link", "click", "tracer_link_cl", "click_cl", "activity", "llm", "job_run", "scrape_log",
        "location")}


def _seed(db, account_id, ids, text, token, persona_id):
    """One row of every account-owned model for `account_id`, every text field = `text`."""
    from backend.models import db as m
    now = datetime.now(timezone.utc)
    with use_account(account_id):
        co_name = f"Co {text}"
        rows = [
            m.Search(id=ids["search"], name=f"Search {text}", search_mode="keyword",
                     search_term=text, sources=["indeed"], title_include_keywords=[text]),
            m.Company(id=ids["company"], name=co_name, scrape_urls=[f"https://{token}.example/{text}"],
                      notes=text, aliases=[f"alias {text}"], tier=1,
                      selected_resume_ids=[str(ids["resume"])]),
            m.Resume(id=ids["resume"], name=f"Resume {text}", is_base=True,
                     json_data={"header": {"name": text}, "summary": text}),
        ]
        db.add_all(rows)
        db.flush()
        db.add(m.Job(
            id=ids["job"], external_id=f"ext-{token}", content_hash=f"hash-{token}",
            company=co_name, title=f"Title {text}", url=_job_url(token),
            source="test", search_id=ids["search"], description=text, location=f"City {text}",
            loc_country="US", loc_city=f"city{token}", status="applied", saved=True, seen=False,
            cv_scores={f"Resume {text}": 81}, best_cv=f"Resume {text}", best_cv_score=81,
            scoring_report={f"Resume {text}": {"summary": text}}, h1b_verdict="likely",
            discovered_at=now - timedelta(days=1)))
        # A second, untouched job: new, unscored, unsaved (the feed's default view and
        # the unscored counters only see jobs like this one).
        db.add(m.Job(
            id=ids["job_new"], external_id=f"ext-new-{token}", content_hash=f"hash-new-{token}",
            company=co_name, title=f"Fresh {text}", url=f"https://{token}.example/new/1",
            source="test", search_id=ids["search"], description=text, status="new",
            discovered_at=now))
        db.flush()
        db.add_all([
            m.JobLocation(id=ids["location"], job_id=ids["job"], country="US",
                          city=f"city{token}", is_primary=True),
            m.Resume(id=ids["tailored"], name=f"Tailored {text}", is_base=False,
                     parent_id=ids["resume"], job_id=ids["job"],
                     json_data={"header": {"name": text}, "_score": {"score": 70}}),
            m.Application(id=ids["application"], job_id=ids["job"], status="interview",
                          notes=text, next_action=text, applied_at=now - timedelta(days=2),
                          status_transitions=[
                              {"from": None, "to": "applied", "at": (now - timedelta(days=2)).isoformat(), "source": "ui"},
                              {"from": "applied", "to": "interview", "at": now.isoformat(), "source": "ui"}]),
        ])
        db.flush()
        db.add_all([
            m.Interview(id=ids["interview"], application_id=ids["application"], what=text,
                        where_text=text, prep=text, when_at=now + timedelta(days=1)),
            m.CoverLetter(id=ids["cover_letter"], name=f"Letter {text}", job_id=ids["job"],
                          resume_id=ids["resume"], json_data={"greeting": text, "body_paragraphs": [text]}),
            m.Persona(id=persona_id, contact={"name": text, "email": f"{token}@example.com"},
                      work_auth={"note": text}, demographics={}, compensation={"note": text},
                      preferences={"note": text}, resume_content={"summary": text},
                      qa_bank=[{"question": text, "answer": text}]),
            m.ActivityLog(id=ids["activity"], type="scrape", message=text, company=co_name,
                          details={"note": text}),
            m.LlmCallLog(id=ids["llm"], purpose="score_light", provider="claude_api",
                         model=f"model-{text}", job_id=ids["job"], input_tokens=100,
                         output_tokens=10, cost_usd=1.25, success=False, error=text),
            m.JobRun(id=ids["job_run"], job_type="scrape_all", trigger="manual",
                     status="completed", started_at=now - timedelta(minutes=5), finished_at=now,
                     duration_seconds=3.0, result_summary=text, meta={"note": text},
                     target_job_id=ids["job"]),
            m.ScrapeLog(id=ids["scrape_log"], search_id=ids["search"], company_id=ids["company"],
                        source="jobspy", jobs_found=3, new_jobs=1, error=text, is_warning=True,
                        source_breakdown={text: 3}),
        ])
        db.flush()
        db.add_all([
            m.TracerLink(id=ids["tracer_link"], token=token, resume_id=ids["resume"],
                         destination_url=f"https://{token}.example/{text}", source_label=text),
            m.TracerLink(id=ids["tracer_link_cl"], token=_cl_token(token),
                         cover_letter_id=ids["cover_letter"],
                         destination_url=f"https://{token}.example/cl/{text}", source_label=text),
        ])
        db.flush()
        db.add_all([
            m.TracerClickEvent(id=ids["click"], tracer_link_id=ids["tracer_link"],
                               referrer_host=f"{token}.{text}"),
            m.TracerClickEvent(id=ids["click_cl"], tracer_link_id=ids["tracer_link_cl"],
                               referrer_host=f"{token}.cl.{text}"),
        ])
        db.commit()
    db.expunge_all()


def _seed_memory_b(ids, b_account):
    """In-memory state that belongs to B: a running monitor entry and a search test result."""
    import backend.job_monitor as jm
    from backend.api import routes_searches as rs
    jm._running[jm._make_key("search_run", str(ids["search"]), b_account)] = jm.RunningJob(
        run_id=ids["job_run"], job_type="search_run", trigger="manual",
        started_at=datetime.now(timezone.utc), scope_key=str(ids["search"]),
        target_job_id=ids["job"], company_id=str(ids["company"]), meta={"search": MARKER},
        account_id=b_account)
    rs._test_results[str(ids["job_run"])] = {"status": "done", "result": {"jobs": [{"title": MARKER}]},
                                             "account": str(b_account)}


def _clear_memory_b(ids):
    import backend.job_monitor as jm
    from backend.api import routes_searches as rs
    for key in [k for k, r in jm._running.items() if r.run_id == ids["job_run"]]:
        jm._running.pop(key, None)
    rs._test_results.pop(str(ids["job_run"]), None)


# ── Snapshots ────────────────────────────────────────────────────────────────

def _owned_models():
    from backend.models.db import AccountScoped, Base
    return sorted((mp.class_ for mp in Base.registry.mappers if issubclass(mp.class_, AccountScoped)),
                  key=lambda c: c.__tablename__)


def _row_dict(obj):
    return {c.key: getattr(obj, c.key) for c in obj.__mapper__.column_attrs}


def _snapshot(account_id):
    """Every row of `account_id` (plus its job locations and tracer clicks), as plain dicts."""
    from backend.models import db as m
    s = m.SessionLocal()
    try:
        with unscoped():
            snap = {}
            for model in _owned_models():
                for row in s.query(model).filter(model.account_id == account_id).all():
                    snap[(model.__tablename__, str(row.id))] = _row_dict(row)
            job_ids = [k[1] for k in snap if k[0] == "jobs"]
            link_ids = [k[1] for k in snap if k[0] == "tracer_links"]
            for row in s.query(m.JobLocation).all():
                if str(row.job_id) in job_ids:
                    snap[("job_locations", str(row.id))] = _row_dict(row)
            for row in s.query(m.TracerClickEvent).all():
                if str(row.tracer_link_id) in link_ids:
                    snap[("tracer_click_events", str(row.id))] = _row_dict(row)
            return snap
    finally:
        s.close()


def _fk_columns(model):
    return [c for c in model.__table__.columns if c.foreign_keys and c.name != "account_id"]


def _a_rows_touching_b(a_id, b_uuids):
    """A rows that point at a B row through a foreign key, or carry B's marker."""
    from backend.models import db as m
    bad = []
    s = m.SessionLocal()
    try:
        with unscoped():
            for model in _owned_models():
                fks = _fk_columns(model)
                for row in s.query(model).filter(model.account_id == a_id).all():
                    for col in fks:
                        v = getattr(row, col.key, None)
                        if v is not None and str(v) in b_uuids:
                            bad.append(f"{model.__tablename__}.{col.name} -> B row {v}")
                    if MARKER in repr(_row_dict(row)):
                        bad.append(f"{model.__tablename__} {row.id} carries B's marker")
    finally:
        s.close()
    return bad


# ── Request building ─────────────────────────────────────────────────────────

def _b_value(kind, b):
    return B_TOKEN if kind == "tracer_token" else (2 if kind == "persona" else str(b[kind]))


def _unwrap(ann):
    origin = typing.get_origin(ann)
    if origin is typing.Union or str(origin) == "types.UnionType":
        args = [a for a in typing.get_args(ann) if a is not type(None)]
        return _unwrap(args[0]) if args else str
    if origin is typing.Annotated:
        return _unwrap(typing.get_args(ann)[0])
    return ann


def _example(name, ann, path, b):
    if name in PARAM_MODELS:
        return _b_value(PARAM_MODELS[name], b)
    if name in PLURAL_PARAMS:
        return [str(b[PLURAL_PARAMS[name]])]
    if name == "url":
        return _job_url(B_TOKEN)
    ann = _unwrap(ann)
    origin = typing.get_origin(ann) or ann
    if origin in (list, tuple, set):
        return []
    if origin is dict:
        return {}
    if ann is bool:
        return False
    if ann is int:
        return 1
    if ann is float:
        return 1.0
    return WRITE_TEXT


def _id_fields(path, b):
    """Every id-ish field a dict body may read, pointing at B's rows."""
    body = {name: _b_value(kind, b) for name, kind in PARAM_MODELS.items()
            if kind not in ("tracer_token", "persona")}
    body.update({name: [str(b[kind])] for name, kind in PLURAL_PARAMS.items()})
    res = _resource_of(path)
    if res:
        body["ids"] = [str(b[res])]
    body["url"] = _job_url(B_TOKEN)   # dedup-by-URL lookups must not find B's job
    return body


def _build_request(route, b):
    """(url, query, json_body, unmapped) for calling `route` as A with B's ids."""
    hints = {}
    try:
        hints = typing.get_type_hints(route.endpoint, include_extras=True)
    except Exception:
        pass
    sig = inspect.signature(route.endpoint)

    unmapped, path_values = [], {}
    for p in route.dependant.path_params:
        if p.name in PARAM_MODELS:
            path_values[p.name] = _b_value(PARAM_MODELS[p.name], b)
        else:
            unmapped.append(p.name)
            path_values[p.name] = "unmapped"
    url = route.path_format.format(**path_values)

    query = {}
    for p in route.dependant.query_params:
        if p.name in PARAM_MODELS:
            query[p.name] = _b_value(PARAM_MODELS[p.name], b)
        elif p.name in PLURAL_PARAMS:
            query[p.name] = str(b[PLURAL_PARAMS[p.name]])

    body = None
    for p in route.dependant.body_params:
        ann = _unwrap(hints.get(p.name, sig.parameters[p.name].annotation if p.name in sig.parameters else dict))
        if inspect.isclass(ann) and issubclass(ann, BaseModel):
            body = {}
            for fname, f in ann.model_fields.items():
                if fname in PARAM_MODELS or fname in PLURAL_PARAMS:
                    body[fname] = _example(fname, f.annotation, route.path, b)
                elif f.is_required():
                    body[fname] = _example(fname, f.annotation, route.path, b)
        elif ann is dict or typing.get_origin(ann) is dict:
            prefix = _prefix_of(route.path)
            writes = dict(WRITE_FIELDS.get(prefix, {}))
            body = {**_id_fields(route.path, b), **writes, "updates": dict(writes)}
        # File / Form parameters: sent empty (the route answers 422)
    return url, query, body, unmapped


def _sent_values(url, query, body):
    blob = url + " " + json.dumps(query) + " " + json.dumps(body)
    return blob


def _b_identifiers(b):
    ids = set()
    for v in b.values():
        ids.add(str(v))
        ids.add(v.hex)
    ids.update({B_TOKEN, _cl_token(B_TOKEN)})
    return ids


def _scan(text, b, sent):
    """B data in `text`: the marker always, B ids unless the request itself sent them."""
    found = []
    if MARKER in text:
        found.append("marker")
    for ident in _b_identifiers(b):
        if ident in text and ident not in sent and ident.replace("-", "") not in sent.replace("-", ""):
            found.append(ident)
    return found


def _normalise(text):
    try:
        text = json.dumps(json.loads(text), sort_keys=True)
    except Exception:
        pass
    return _TS_RE.sub("<ts>", _UUID_RE.sub("<uuid>", text))


# ── Stubs: no network, no LLM, no browser, no background work ────────────────

@pytest.fixture
def launches(monkeypatch):
    """Record background launches instead of running them."""
    calls = []

    def _launch(job_type, coro_func, *args, **kwargs):
        calls.append(repr((job_type, args, kwargs)))
        return str(uuid.uuid4())

    import backend.job_monitor as jm
    import backend.main as main_mod
    from backend.api import routes_cover_letters, routes_jobs, routes_linkedin, routes_resumes
    for mod in (jm, main_mod, routes_jobs, routes_cover_letters, routes_linkedin, routes_resumes):
        monkeypatch.setattr(mod, "launch_background", _launch, raising=False)

    from starlette.background import BackgroundTasks

    def _add_task(self, func, *args, **kwargs):
        calls.append(repr((getattr(func, "__name__", str(func)), args, kwargs)))
    monkeypatch.setattr(BackgroundTasks, "add_task", _add_task)
    return calls


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    import httpx

    def _no_network(*a, **k):
        raise RuntimeError("network disabled in the leak harness")
    monkeypatch.setattr(httpx, "AsyncClient", _no_network)

    from backend.analyzer import llm_client

    async def _dispatch(*a, **k):
        return {"text": "{}", "usage": {"input_tokens": 0, "output_tokens": 0,
                                        "cache_read_tokens": 0, "cache_write_tokens": 0}}

    async def _stream(*a, **k):
        yield "ok"
    monkeypatch.setattr(llm_client, "_dispatch", _dispatch)
    monkeypatch.setattr(llm_client, "_stream_claude", _stream)
    monkeypatch.setattr(llm_client, "_stream_openai", _stream)

    async def _no_browser(*a, **k):
        raise RuntimeError("browser disabled in the leak harness")
    from backend.scraper._shared import browser
    from backend.api import routes_resumes
    monkeypatch.setattr(browser, "_get_browser", _no_browser)
    monkeypatch.setattr(routes_resumes, "_get_browser", _no_browser)

    import jobspy
    monkeypatch.setattr(jobspy, "scrape_jobs", _no_network)

    # The Gmail OAuth client comes from .env; pin it so /gmail/connect answers the same with
    # or without one (CI has none and got a 503 that proves nothing).
    from backend.email_monitor import gmail_client
    monkeypatch.setattr(gmail_client, "GMAIL_CLIENT_ID", "leak-harness-client")
    monkeypatch.setattr(gmail_client, "GMAIL_CLIENT_SECRET", "leak-harness-secret")
    monkeypatch.setattr(gmail_client, "GMAIL_REFRESH_TOKEN", "")


# ── The cases ────────────────────────────────────────────────────────────────

@pytest.fixture
def accounts(test_db):
    from backend.models.db import Account
    a = test_db.query(Account).filter(Account.role == "owner").one()
    b = Account(name=f"Member {MARKER}", role="member", color="#888888")
    test_db.add(b)
    test_db.commit()
    return a.id, b.id


DIRECTIONS = ("owner-via-header", "member-via-cookie")


def _act_as(client, direction, caller_id):
    """Make `client` act as the caller through a real MT-10 auth path."""
    if direction == "owner-via-header":
        client.cookies.clear()
        client.headers.pop("X-Test-Act-As", None)
        client.headers["X-Account-Token"] = account_token(caller_id)
    else:
        client.headers.pop("X-Test-Act-As", None)
        client.headers.pop("X-Account-Token", None)
        r = client.post("/api/auth/switch", json={"account_id": str(caller_id)})
        assert r.status_code == 200, r.text
        assert client.cookies.get("jn_account")
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["account"]["id"] == str(caller_id), me.text


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("method,path", _route_cases())
def test_route_does_not_leak_b(method, path, direction, client, test_db, accounts, launches):
    """Caller A, victim B (B's rows carry MARKER). owner-via-header: A = owner with the
    X-Account-Token, B = member. member-via-cookie: A = member with the jn_account
    cookie from POST /api/auth/switch, B = owner."""
    owner_id, member_id = accounts
    a_id, b_id = (owner_id, member_id) if direction == DIRECTIONS[0] else (member_id, owner_id)
    from backend.models.db import Account
    for acc_id, name in ((a_id, "Caller account"), (b_id, f"Victim {MARKER}")):
        test_db.query(Account).filter(Account.id == acc_id).update({"name": name})
    test_db.commit()
    _act_as(client, direction, a_id)
    route = next(r for m, p, r in _api_routes() if (m, p) == (method, path))
    a_ids, b = _ids(), _ids()
    _seed(test_db, a_id, a_ids, A_TEXT, A_TOKEN, persona_id=1)

    url, query, body, unmapped = _build_request(route, b)
    if unmapped:
        pytest.fail(f"unmapped path parameter(s) {unmapped}: add them to PARAM_MODELS")
    sent = _sent_values(url, query, body)

    def call():
        kw = {"params": query}
        if body is not None:
            kw["json"] = body
        return client.request(method, url, follow_redirects=False, **kw)

    def text_of(resp):
        return resp.content.decode("utf-8", "ignore") + " " + resp.headers.get("location", "")

    problems = []
    before = None
    if method == "GET":
        r0a, r0b = call(), call()
        if _normalise(text_of(r0a)) == _normalise(text_of(r0b)):
            before = (r0a.status_code, _normalise(text_of(r0a)))

    _seed(test_db, b_id, b, MARKER, B_TOKEN, persona_id=2)
    _seed_memory_b(b, b_id)
    snap = _snapshot(b_id)
    launches.clear()
    try:
        resp = call()
    finally:
        _clear_memory_b(b)

    text = text_of(resp)
    if resp.status_code >= 500:
        # A route that errors (often Postgres-only SQL on the SQLite test DB) proves nothing.
        problems.append(f"inconclusive: {resp.status_code} {text[:200]}")
    if resp.status_code not in (403, 404, 422):
        hits = _scan(text, b, sent)
        if hits:
            problems.append(f"response {resp.status_code} carries B data {hits[:3]}: {text[:300]}")
    if before is not None:
        after = (resp.status_code, _normalise(text))
        if after != before:
            problems.append(f"answer changed once B's rows exist: {before[0]} -> {after[0]}: "
                            f"{before[1][:200]} || {after[1][:200]}")
    after_snap = _snapshot(b_id)
    if after_snap != snap:
        changed = sorted(set(snap) ^ set(after_snap)) + sorted(
            k for k in set(snap) & set(after_snap) if snap[k] != after_snap[k])
        problems.append(f"B's rows changed: {changed[:5]}")
    b_uuids = {str(v) for v in b.values()}
    problems += _a_rows_touching_b(a_id, b_uuids)
    for call_repr in launches:
        if MARKER in call_repr or any(i in call_repr for i in b_uuids):
            problems.append(f"background work launched on B's data: {call_repr[:200]}")

    assert not problems, f"{method} {path} leaks across accounts:\n  " + "\n  ".join(problems)


# ── Harness self-checks ──────────────────────────────────────────────────────

def test_every_account_owned_model_is_seeded(test_db, accounts):
    """A new account-owned model must get a row in _seed, or the harness cannot see it."""
    a_id, b_id = accounts
    b = _ids()
    _seed(test_db, b_id, b, MARKER, B_TOKEN, persona_id=2)
    seeded = {k[0] for k in _snapshot(b_id)}
    missing = {m.__tablename__ for m in _owned_models()} - seeded
    assert not missing, f"seed a row of {sorted(missing)} in test_mt_leaks._seed"
    assert {"job_locations", "tracer_click_events"} <= seeded


def test_every_path_parameter_is_mapped():
    unmapped = sorted({f"{m} {p}: {{{prm.name}}}" for m, p, r in _api_routes()
                       if (m, p) not in ALLOWLIST
                       for prm in r.dependant.path_params if prm.name not in PARAM_MODELS})
    assert not unmapped, f"unmapped path parameters (add to PARAM_MODELS): {unmapped}"


def test_allowlist_and_known_leaks_name_real_routes():
    routes = {(m, p) for m, p, _ in _api_routes()}
    assert not set(ALLOWLIST) - routes, f"stale allow-list entries: {set(ALLOWLIST) - routes}"
    assert not set(KNOWN_LEAKS) - routes, f"stale KNOWN_LEAKS entries: {set(KNOWN_LEAKS) - routes}"
    assert not set(ALLOWLIST) & set(KNOWN_LEAKS)
    assert all(v.split(":")[0] in ("MT-4", "MT-5", "MT-6") for v in KNOWN_LEAKS.values())
