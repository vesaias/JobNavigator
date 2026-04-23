"""Seed settings and companies tables with defaults on first run."""
import logging
import json
import secrets
from backend.models.db import SessionLocal, Setting, Company, Search, CV, Resume
from sqlalchemy import text

logger = logging.getLogger("jobnavigator.seed")


DEFAULT_SETTINGS = {
    "fit_score_threshold": ("60", "Minimum fit score to trigger Telegram alert"),
    "scrape_interval_minutes": ("60", "How often the job checker runs"),
    "email_check_interval_minutes": ("30", "How often Gmail is polled"),
    "telegram_enabled": ("false", "Toggle all Telegram notifications on/off"),
    "digest_cron": ("0 8 * * *", "Daily digest cron (min hour day month dow). Empty = disabled"),
    "telegram_chat_id": ("", "Your Telegram chat ID"),
    "telegram_webhook_secret": ("", "Auto-generated secret token validated on every /api/telegram/webhook call. Rotate from the Telegram settings tab."),
    "body_exclusion_phrases": (json.dumps([]), "JD phrases that flag exclusion (H-1B, language, etc.). Add phrases to auto-skip jobs containing them."),
    "h1b_cron": ("0 2 * * 0", "H-1B refresh cron (min hour day month dow). Empty = disabled"),
    "cleanup_cron": ("0 4 * * *", "Job cleanup cron (min hour day month dow). Empty = disabled"),
    "job_archive_after_days": ("90", "Delete skipped jobs older than N days (used by cleanup job)"),
    "auto_reject_after_days": ("0", "Reject applications older than N days, 0 = disabled (used by reject job)"),
    "proxy_url": ("", "Optional rotating proxy for scraping"),
    "max_jobs_per_scrape": ("50", "Max results per source per search per run"),
    "dashboard_api_key": ("", "Dashboard password — changeable from dashboard"),
    "company_domains": (json.dumps([
        "microsoft.com", "salesforce.com", "servicenow.com", "workday.com",
        "paypal.com", "jpmorganchase.com", "jpmorgan.com", "blackrock.com",
        "addepar.com", "oracle.com", "intuit.com", "google.com", "amazon.com",
        "stripe.com", "visa.com", "mastercard.com", "uber.com", "block.xyz",
        "plaid.com", "clearstreet.io", "simcorp.com", "cisco.com", "ibm.com",
        "meta.com", "apple.com", "databricks.com", "coinbase.com", "bloomberg.net",
        "robinhood.com", "affirm.com", "kraken.com", "chime.com", "ramp.com",
        "brex.com", "rippling.com"
    ]), "Known company email domains for Gmail detection"),
    "ats_domains": (json.dumps([
        "greenhouse.io", "lever.co", "workday.com", "taleo.net",
        "icims.com", "myworkdayjobs.com"
    ]), "ATS domains"),
    "default_cv_id": ("", "Default CV ID used for scoring when no company-level CVs are configured"),
    "company_exclude_global": (json.dumps([]), "Global company ignore list — applies to all searches"),
    "title_exclude_global": (json.dumps([]), "Global title exclude keywords — applies to all searches and companies"),
    "linkedin_email": ("", "LinkedIn account email for personal scrape mode"),
    "linkedin_password": ("", "LinkedIn account password for personal scrape mode"),
    "linkedin_mock_email": ("", "LinkedIn mock account email for Extension Voyager API"),
    "linkedin_mock_password": ("", "LinkedIn mock account password for Extension Voyager API"),
    "jobright_email": ("", "Jobright.ai account email"),
    "jobright_password": ("", "Jobright.ai account password"),
    "jobright_session_id": ("", "Jobright.ai session cookie (auto-managed, 60-day expiry)"),
    "reject_cron": ("0 4 * * *", "Auto-reject cron (min hour day month dow). Empty = disabled"),
    "backup_cron": ("0 3 * * *", "Backup cron schedule (min hour day month dow). Empty = disabled"),
    "scoring_rubric": ("Score each CV using these criteria (each 0-20, sum to 0-100):\n1. SKILLS MATCH (weight: 20): How many required technical skills/tools does the candidate have?\n2. EXPERIENCE LEVEL (weight: 20): Does seniority/years match? (entry-level CV for senior role = low)\n3. DOMAIN FIT (weight: 20): Has the candidate worked in the same industry/domain?\n4. ROLE ALIGNMENT (weight: 20): Does the candidate's career trajectory match this role type?\n5. REQUIREMENTS MET (weight: 20): Does the candidate meet stated requirements (education, certs, clearance)?\n\nUse the FULL 0-100 range. 90+ = perfect match. 50-70 = decent with gaps. Below 30 = poor match.\nAvoid clustering scores — differentiate meaningfully between CVs and jobs.", "Editable CV scoring rubric"),
    "scoring_output_light": ('Return ONLY this JSON:\n{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "best_cv": "CV_NAME"\n}', "Light scoring output schema"),
    "scoring_output_full": ('Return ONLY this JSON:\n{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "best_cv": "CV_NAME",\n  "summary": "2-3 sentence assessment of candidate-job fit",\n  "requirement_mapping": [\n    {"requirement": "JD requirement text", "cv_match": "matching CV line or null", "matched": true/false, "severity": "required or preferred"}\n  ],\n  "keyword_coverage_pct": 0-100,\n  "matched_keywords": ["keyword1", "keyword2"],\n  "missing_keywords": ["keyword3", "keyword4"],\n  "hard_blockers": ["blocker if any"],\n  "ats_tip": "one actionable ATS optimization suggestion"\n}', "Full scoring output schema with keyword analysis"),
    "llm_provider": ("claude_api", "LLM provider: claude_api, claude_code, openai, ollama, openai_compat"),
    "llm_model": ("claude-sonnet-4-6", "LLM model name"),
    "llm_api_key": ("", "API key for OpenAI/OpenRouter (not needed for Claude API/Ollama)"),
    "llm_base_url": ("", "Custom API endpoint (only for openai_compat)"),
    "llm_fallback_provider": ("", "Fallback LLM provider (empty = no fallback)"),
    "llm_fallback_model": ("", "Fallback model name"),
    "llm_fallback_api_key": ("", "API key for fallback provider (OpenAI/OpenRouter)"),
    "llm_fallback_base_url": ("", "Custom API endpoint for fallback (only for openai_compat)"),
    "llm_models_list": (json.dumps([
        {"provider": "claude_api", "model": "claude-sonnet-4-6"},
        {"provider": "claude_api", "model": "claude-opus-4-6"},
        {"provider": "claude_api", "model": "claude-haiku-4-5-20251001"},
        {"provider": "claude_code", "model": "claude-sonnet-4-6"},
        {"provider": "claude_code", "model": "claude-opus-4-6"},
        {"provider": "claude_code", "model": "claude-haiku-4-5-20251001"},
        {"provider": "openai", "model": "gpt-5.4"},
        {"provider": "openai", "model": "gpt-5.4-mini"},
        {"provider": "openai", "model": "gpt-5.4-nano"},
        {"provider": "openai", "model": "gpt-5.3-codex"},
        {"provider": "openai", "model": "gpt-5.2"},
        {"provider": "openai", "model": "gpt-4o"},
        {"provider": "openai", "model": "gpt-4o-mini"},
        {"provider": "openai", "model": "o3"},
        {"provider": "openai", "model": "o3-mini"},
        {"provider": "openai", "model": "o4-mini"},
        {"provider": "ollama", "model": "llama3.3:70b"},
        {"provider": "ollama", "model": "llama3.1:8b"},
        {"provider": "ollama", "model": "qwen2.5:32b"},
        {"provider": "ollama", "model": "qwen2.5-coder:7b"},
        {"provider": "ollama", "model": "deepseek-r1:14b"},
        {"provider": "ollama", "model": "mistral:7b"},
        {"provider": "ollama", "model": "gemma2:9b"},
        {"provider": "ollama", "model": "phi3:14b"},
        {"provider": "openai_compat", "model": "anthropic/claude-sonnet-4-6"},
        {"provider": "openai_compat", "model": "anthropic/claude-opus-4-6"},
        {"provider": "openai_compat", "model": "openai/gpt-5.4"},
        {"provider": "openai_compat", "model": "openai/o3"},
        {"provider": "openai_compat", "model": "openai/o4-mini"},
        {"provider": "openai_compat", "model": "google/gemini-3.1-pro-preview"},
        {"provider": "openai_compat", "model": "google/gemini-2.5-flash"},
        {"provider": "openai_compat", "model": "meta-llama/llama-3.3-70b-instruct"},
        {"provider": "openai_compat", "model": "deepseek/deepseek-r1"},
        {"provider": "openai_compat", "model": "qwen/qwen-2.5-72b-instruct"},
    ]), "Known LLM models per provider (JSON array, user can add custom entries)"),
    "scoring_max_concurrent": ("5", "Max parallel scoring jobs (others queue until a slot opens)"),
    "prompt_caching_enabled": ("true", "Use Anthropic prompt caching on CV scoring (claude_api only; ~50% cheaper input tokens on same-batch calls). Set false to disable as a rollback lever."),
    "scoring_default_depth": ("light", "Default scoring depth: light or full"),
    "on_save_action": ("off", "Action when job is saved: off, light, or full"),
    "email_llm_enabled": ("false", "Enable LLM second pass for ambiguous email classification"),
    "email_llm_provider": ("", "LLM provider for email classification (empty = use primary llm_provider)"),
    "email_llm_model": ("", "LLM model for email classification (empty = use primary llm_model)"),
    "email_llm_api_key": ("", "API key for email LLM provider"),
    "email_llm_confidence_threshold": ("70", "Min confidence (0-100) to auto-act on LLM email classification"),
    "email_llm_prompt": ("Classify this email and match it to one active application if possible.\n\nRules:\n- match_index: pick from the numbered applications below (1-based), or null if no match\n- status: one of: interview, offer, rejected, no_change\n- confidence: 0-100 how sure you are about classification AND match combined\n- summary: one sentence describing what the email is about\n\nActive applications:\n{applications}\n\nEmail:\nFrom: {from}\nSubject: {subject}\nBody:\n{body}\n\nReturn ONLY this JSON:\n{\"match_index\": null, \"status\": \"no_change\", \"confidence\": 0, \"summary\": \"\"}", "Editable email classification LLM prompt template"),
    "email_gmail_query_subjects": (json.dumps([
        "application", "thank you for applying", "thanks for applying",
        "application received", "application submitted", "your application",
        "interview", "assessment", "coding challenge", "take-home",
        "availability", "offer", "offer letter", "referral", "recruiter",
        "hiring team", "regret to inform", "not moving forward", "not selected",
        "application unsuccessful", "moving forward with other candidates",
        "unable to proceed", "position has been filled", "hiring freeze",
        "position on hold", "withdrawn"
    ]), "Subject keywords for Gmail search query"),
    "email_gmail_query_senders": (json.dumps([
        "careers@", "jobs@", "recruiting@", "talent@",
        "no-reply@greenhouse.io", "no-reply@us.greenhouse-mail.io",
        "no-reply@ashbyhq.com", "notification@smartrecruiters.com",
        "@smartrecruiters.com", "@workablemail.com", "@hire.lever.co",
        "@myworkday.com", "@workdaymail.com", "@greenhouse.io", "@ashbyhq.com"
    ]), "Sender patterns for Gmail search query"),
    "email_gmail_query_exclusions": (json.dumps([
        "newsletter", "webinar", "course", "discount",
        "event invitation", "job search council", "matched new opportunities"
    ]), "Subject terms to exclude from Gmail search query"),
    "cv_tailor_llm_provider": ("", "LLM provider for CV tailoring (empty = use primary llm_provider)"),
    "cv_tailor_llm_model": ("", "LLM model for CV tailoring (empty = use primary llm_model)"),
    "cv_tailor_llm_api_key": ("", "API key for CV tailoring LLM provider"),
    "cv_tailor_prompt": ("Tailor this resume for the job description below.\n\nRules:\n- Rewrite the summary to target this specific role\n- For each experience bullet: if it benefits from JD keyword alignment, reformulate it. If it's already well-suited, leave it UNCHANGED\n- Keep the same number of bullets per experience entry - do not add or remove\n- Reorder skills to prioritize JD-relevant ones first\n- For each experience entry, suggest 1-2 additional bullets derived from existing content (reframed for the JD). Each suggested bullet MUST follow the STAR format: lead with a strong action verb, include context, and anchor with a concrete metric or measurable outcome\n- Do NOT invent new experience, skills, or facts. If something is missing, map to the closest truthful concept\n- NEVER add skills the candidate does not have\n- Preserve all company names, titles, dates, locations, education exactly\n- Do NOT use em-dashes or unicode special characters. Use regular hyphens (-) and ASCII only\n- Preserve **bold** formatting (double asterisks) from the original bullets. For reformulated bullets, wrap the strongest metric or achievement in **bold** (e.g. **40,000+ new clients**, **reduced error rates by 30%**). Each bullet should have at most one bold highlight\n- VERIFICATION: After generating, verify each reformulated bullet and suggestion is traceable to the original resume content. If you cannot trace it to existing experience, remove it\n\nResume:\n{resume_json}\n\nJob Description:\n{job_description}\n\nReturn ONLY this JSON:\n{\"summary\": \"rewritten summary\", \"experience\": [{\"company\": \"unchanged\", \"title\": \"unchanged\", \"location\": \"unchanged\", \"date\": \"unchanged\", \"description\": \"unchanged or null\", \"bullets\": [\"reformulated or unchanged bullet\"], \"suggested_bullets\": [\"new suggested bullet\"]}], \"skills\": {\"reordered label\": \"reordered value\"}}", "Editable CV tailoring LLM prompt template"),
    "tracer_links_enabled": ("false", "Enable URL rewriting in PDF generation with tracking links"),
    "tracer_links_base_url": ("", "Public base URL for tracer links (e.g., https://yourdomain.com)"),
    "tracer_links_url_style": ("path", "URL format: path or param. Token: random or job_id. Combinations: path, param, path_jobid, param_jobid"),
    "dedup_tracking_params": (json.dumps([
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "mode",
        "src", "source", "ref", "refid", "refsrc", "refsource",
        "origin", "from", "channel", "medium",
        "gns", "gnk", "gni",
        "trk", "trackingid", "tracking_id", "currentjobid",
        "ebp", "recommendedflavor",
        "gh_src", "lever_source", "lever_origin",
        "lever-source", "lever-origin", "lever-source[]", "lever-source%5b%5d",
        "visitid", "impid",
        "jz",
        "iis", "iisn",
        "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
        "_ga", "_gl", "dclid", "zanpid",
        "igshid", "yclid", "twclid",
        "_hsenc", "_hsmi", "mkt_tok",
        "jclickid", "publisher",
        "p_sid", "p_uid", "ss",
        "__jvsd", "__jvst", "jobpipeline", "cmpid", "codes", "feedid",
        "partnerid", "siteid", "bid", "customredirect",
        "chnlid", "v", "ccd", "frd", "r", "a",
        "jk",
    ]), "URL query params stripped before dedup hashing — tracking/referral noise"),
}

SEED_COMPANIES = [
    # Example companies — one per ATS type. All inactive by default.
    # Greenhouse
    {"name": "Cloudflare", "tier": 2, "scrape_urls": ["https://boards.greenhouse.io/cloudflare"]},
    # Greenhouse
    {"name": "Anthropic", "tier": 1, "scrape_urls": ["https://job-boards.greenhouse.io/anthropic"]},
    # Ashby
    {"name": "OpenAI", "tier": 1, "scrape_urls": ["https://jobs.ashbyhq.com/openai/"]},
    # Workday
    {"name": "Salesforce", "tier": 1, "scrape_urls": ["https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site?CF_-_REC_-_LRV_-_Job_Posting_Anchor_-_Country_from_Job_Posting_Location_Extended=bc33aa3152ec42d4995f4791a106ed09"]},
    # Lever
    {"name": "Plaid", "tier": 2, "scrape_urls": ["https://jobs.lever.co/plaid"]},
    # Rippling
    {"name": "Rippling", "tier": 3, "scrape_urls": ["http://ats.rippling.com/rippling/jobs?workLocation=United+States"]},
    # Meta Careers (Playwright DOM)
    {"name": "Meta", "tier": 2, "scrape_urls": ["https://www.metacareers.com/jobsearch?offices[0]=Menlo%20Park%2C%20CA&teams[0]=Technical%20Program%20Management&teams[1]=Product%20Management&sort_by_new=true"]},
    # Google Careers (Playwright DOM)
    {"name": "Google", "tier": 2, "scrape_urls": ["https://www.google.com/about/careers/applications/jobs/results?location=United%20States"]},
    # Apple (API)
    {"name": "Apple", "tier": 2, "scrape_urls": ["https://jobs.apple.com/en-us/search?sort=relevance&location=united-states-USA"]},
    # Oracle HCM
    {"name": "Oracle", "tier": 3, "scrape_urls": ["https://careers.oracle.com/en/sites/jobsearch/jobs?lastSelectedFacet=LOCATIONS&selectedLocationsFacet=300000000149325"]},
    # Phenom People
    {"name": "Cisco", "tier": 3, "scrape_urls": ["POST|https://careers.cisco.com/widgets|{\"sortBy\":\"\",\"subsearch\":\"\",\"jobs\":true,\"counts\":true,\"all_fields\":[\"category\",\"raasJobRequisitionType\",\"country\",\"state\",\"city\",\"type\",\"RemoteType\"],\"pageName\":\"search-results\",\"clearAll\":false,\"jdsource\":\"facets\",\"isSliderEnable\":false,\"pageId\":\"page4\",\"siteType\":\"external\",\"keywords\":\"\",\"global\":true,\"selected_fields\":{\"raasJobRequisitionType\":[\"Professional\"],\"country\":[\"United States of America\"]},\"lang\":\"en_global\",\"deviceType\":\"desktop\",\"country\":\"global\",\"refNum\":\"CISCISGLOBAL\"}"]},
    # TalentBrew
    {"name": "Intuit", "tier": 2, "scrape_urls": ["https://jobs.intuit.com/search-jobs/results?ActiveFacetID=6252001-5332921&CurrentPage=1&RecordsPerPage=15&TotalContentResults=&Distance=50&RadiusUnitType=0&Keywords=&Location=United+States&ShowRadius=False&IsPagination=False&CustomFacetName=&FacetTerm=&FacetType=0&FacetFilters%5B0%5D.ID=6252001-5332921&FacetFilters%5B0%5D.FacetType=3&FacetFilters%5B0%5D.Count=435&FacetFilters%5B0%5D.Display=California%2C+United+States&FacetFilters%5B0%5D.IsApplied=true&FacetFilters%5B0%5D.FieldName=&SearchResultsModuleName=Search+Results&SearchFiltersModuleName=Search+Filters&SortCriteria=0&SortDirection=0&SearchType=1&OrganizationIds=27595&PostalCode=&ResultsType=0&fc=&fl=&fcf=&afc=&afl=&afcf=&TotalContentPages=NaN"]},
]


def seed_settings(db):
    """Insert default settings if they don't exist."""
    existing = {s.key for s in db.query(Setting).all()}
    for key, (value, desc) in DEFAULT_SETTINGS.items():
        if key not in existing:
            db.add(Setting(key=key, value=value, description=desc))
    db.commit()
    # One-shot: ensure the Telegram webhook secret has a cryptographically random
    # value. We seed an empty string above so operators can see the row exists in
    # /api/settings; the real value is generated here on first run (or if the
    # operator manually clears it to force a rotation).
    row = db.query(Setting).filter(Setting.key == "telegram_webhook_secret").first()
    if row is not None and not (row.value or "").strip():
        row.value = secrets.token_urlsafe(32)
        db.commit()


def seed_companies(db):
    """Insert seed companies if table is empty."""
    if db.query(Company).count() > 0:
        return
    for c in SEED_COMPANIES:
        db.add(Company(
            name=c["name"],
            tier=c.get("tier"),
            scrape_urls=c["scrape_urls"],
            active=False,
            playwright_enabled=True,
        ))
    db.commit()


H1B_SLUG_OVERRIDES = {
    # Add H-1B slug overrides for MyVisaJobs.com lookups. Example:
    # "Acme Corp": "acme-corporation",
}


def run_migrations(db):
    """Run ALTER TABLE migrations for columns that create_all() won't add to existing tables."""
    migrations = [
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS h1b_slug VARCHAR",
        "ALTER TABLE searches ADD COLUMN IF NOT EXISTS company_exclude JSONB DEFAULT '[]'",
        "ALTER TABLE searches ADD COLUMN IF NOT EXISTS max_pages INTEGER DEFAULT 50",
        "ALTER TABLE companies ALTER COLUMN tier DROP NOT NULL",
        "ALTER TABLE companies ALTER COLUMN tier SET DEFAULT NULL",
        "ALTER TABLE jobs DROP COLUMN IF EXISTS language_flag",
        "ALTER TABLE jobs DROP COLUMN IF EXISTS language_snippet",
        "ALTER TABLE searches ADD COLUMN IF NOT EXISTS require_salary BOOLEAN DEFAULT FALSE",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS scoring_report JSONB",
        "ALTER TABLE jobs DROP COLUMN IF EXISTS fit_summary",
        "ALTER TABLE jobs DROP COLUMN IF EXISTS fit_strengths",
        "ALTER TABLE jobs DROP COLUMN IF EXISTS fit_gaps",
        "ALTER TABLE searches ADD COLUMN IF NOT EXISTS auto_keyword BOOLEAN DEFAULT FALSE",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS auto_keyword BOOLEAN DEFAULT FALSE",
        "ALTER TABLE jobs DROP COLUMN IF EXISTS apply_recommendation",
        "ALTER TABLE searches ADD COLUMN IF NOT EXISTS auto_scoring_depth VARCHAR DEFAULT 'off'",
        "ALTER TABLE searches DROP COLUMN IF EXISTS auto_score",
        "ALTER TABLE searches DROP COLUMN IF EXISTS auto_keyword",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS auto_scoring_depth VARCHAR DEFAULT 'off'",
        "ALTER TABLE companies DROP COLUMN IF EXISTS auto_score",
        "ALTER TABLE companies DROP COLUMN IF EXISTS auto_keyword",
        "CREATE TABLE IF NOT EXISTS resumes (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR NOT NULL, is_base BOOLEAN DEFAULT TRUE, parent_id UUID REFERENCES resumes(id) ON DELETE SET NULL, job_id UUID REFERENCES jobs(id) ON DELETE SET NULL, template VARCHAR DEFAULT 'garamond', page_format VARCHAR DEFAULT 'letter', json_data JSONB DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS tracer_links (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token VARCHAR(10) UNIQUE NOT NULL, resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE, destination_url VARCHAR NOT NULL, source_label VARCHAR NOT NULL, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_tracer_links_token ON tracer_links(token)",
        "CREATE TABLE IF NOT EXISTS tracer_click_events (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tracer_link_id UUID NOT NULL REFERENCES tracer_links(id) ON DELETE CASCADE, clicked_at TIMESTAMPTZ DEFAULT NOW() NOT NULL, device_type VARCHAR DEFAULT 'unknown', ua_family VARCHAR DEFAULT 'unknown', os_family VARCHAR DEFAULT 'unknown', referrer_host VARCHAR, ip_hash VARCHAR, is_likely_bot BOOLEAN DEFAULT FALSE)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS short_id INTEGER UNIQUE",
        "CREATE SEQUENCE IF NOT EXISTS jobs_short_id_seq START 1",
        "ALTER TABLE jobs ALTER COLUMN short_id SET DEFAULT nextval('jobs_short_id_seq')",
        """CREATE TABLE IF NOT EXISTS llm_call_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            purpose VARCHAR NOT NULL,
            job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
            model VARCHAR NOT NULL DEFAULT '',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cache_read_tokens INTEGER NOT NULL DEFAULT 0,
            cache_write_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd FLOAT NOT NULL DEFAULT 0.0,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            error TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_llm_call_log_created_at ON llm_call_log(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_llm_call_log_purpose ON llm_call_log(purpose)",
        "CREATE INDEX IF NOT EXISTS ix_llm_call_log_job_id ON llm_call_log(job_id)",
        # Fix FK drift: the CREATE TABLE above is a no-op on live DBs where SQLAlchemy's
        # create_all() already built the table with no ondelete (NO ACTION). Re-align
        # the live constraint to ON DELETE SET NULL. Safe idempotent SQL.
        """ALTER TABLE llm_call_log DROP CONSTRAINT IF EXISTS llm_call_log_job_id_fkey""",
        """ALTER TABLE llm_call_log ADD CONSTRAINT llm_call_log_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL""",
        "ALTER TABLE llm_call_log ADD COLUMN IF NOT EXISTS provider VARCHAR NOT NULL DEFAULT ''",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS best_cv_score FLOAT",
        "CREATE INDEX IF NOT EXISTS ix_jobs_best_cv_score ON jobs(best_cv_score)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cache_error TEXT",
        """UPDATE jobs SET best_cv_score = (
            SELECT MAX(CAST(value AS FLOAT))
            FROM jsonb_each_text(cv_scores)
            WHERE value ~ '^[0-9]+(\\.[0-9]+)?$'
        ) WHERE cv_scores IS NOT NULL
          AND jsonb_typeof(cv_scores) = 'object'
          AND cv_scores != '{}'
          AND best_cv_score IS NULL""",
        # 2026-04-23: Retire screening / phone_screen / final_round statuses.
        # Board collapses to applied / interview / offer / rejected. Existing
        # row statuses are remapped; status_transitions history is preserved
        # as-is so the audit trail still shows the original transitions.
        "UPDATE applications SET status = 'applied' WHERE status = 'screening'",
        "UPDATE applications SET status = 'interview' WHERE status IN ('phone_screen', 'final_round')",
    ]
    for sql in migrations:
        try:
            db.execute(text(sql))
        except Exception as e:
            logger.warning(f"Migration skipped: {e}")
    db.commit()

    _rewrite_retired_status_transitions(db)


_RETIRED_STATUS_REMAP = {
    "screening": "applied",
    "phone_screen": "interview",
    "final_round": "interview",
}


def _rewrite_retired_status_transitions(db):
    """One-shot: rewrite Application.status_transitions JSON to match the
    2026-04-23 status-ladder simplification. Remaps retired statuses, drops
    self-transitions that result from the remap, and collapses consecutive
    duplicates so the Sankey diagram no longer shows ghost `screening` /
    `phone_screen` / `final_round` nodes.

    Idempotent: scans only rows that still contain a retired label.
    """
    from backend.models.db import Application
    retired = tuple(_RETIRED_STATUS_REMAP)
    rows = db.query(Application).filter(
        Application.status_transitions.isnot(None)
    ).all()
    changed = 0
    for app in rows:
        tx = app.status_transitions or []
        if not any(
            (t.get("from") in retired or t.get("to") in retired) for t in tx
        ):
            continue

        rewritten: list[dict] = []
        for t in tx:
            new_from = _RETIRED_STATUS_REMAP.get(t.get("from"), t.get("from"))
            new_to = _RETIRED_STATUS_REMAP.get(t.get("to"), t.get("to"))
            # Drop self-transitions (e.g. applied → applied after remap).
            if new_from == new_to:
                continue
            rewritten.append({**t, "from": new_from, "to": new_to})

        # Collapse consecutive entries where prev.to == curr.to (same target
        # reached twice in a row, e.g. applied→interview→interview).
        collapsed: list[dict] = []
        for t in rewritten:
            if collapsed and collapsed[-1].get("to") == t.get("to"):
                continue
            collapsed.append(t)

        if collapsed != tx:
            app.status_transitions = collapsed
            changed += 1
    if changed:
        db.commit()
        logger.info(
            f"Status-transition cleanup: rewrote {changed} application rows to "
            f"drop retired screening/phone_screen/final_round entries"
        )


def seed_h1b_slugs(db):
    """Migrate hardcoded H-1B slug overrides into Company records."""
    for name, slug in H1B_SLUG_OVERRIDES.items():
        company = db.query(Company).filter(Company.name == name).first()
        if company and not company.h1b_slug:
            company.h1b_slug = slug
    db.commit()


def cleanup_removed_settings(db):
    """Remove settings that have been removed from DEFAULT_SETTINGS."""
    removed_keys = ["followup_reminder_days", "h1b_exclusion_phrases", "language_exclude_phrases"]
    for key in removed_keys:
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            db.delete(row)
    db.commit()


SEED_SEARCHES = [
    {
        "name": "LinkedIn Extension",
        "active": True,
        "search_mode": "linkedin_extension",
        "sources": [],
        "title_include_keywords": [],
        "title_exclude_keywords": [],
        "company_exclude": [],
        "auto_scoring_depth": "off",
    },
    {
        "name": "Keyword Search",
        "active": False,
        "search_mode": "keyword",
        "sources": ["linkedin", "indeed", "zip_recruiter", "google"],
        "title_include_keywords": ["product manager", "program manager"],
        "title_exclude_keywords": [],
        "company_exclude": [],
        "auto_scoring_depth": "off",
    },
    {
        "name": "Levels.fyi",
        "active": False,
        "search_mode": "levels_fyi",
        "sources": [],
        "title_include_keywords": [],
        "title_exclude_keywords": [],
        "company_exclude": [],
        "auto_scoring_depth": "off",
    },
    {
        "name": "LinkedIn Personal",
        "active": False,
        "search_mode": "linkedin_personal",
        "sources": ["recommended", "top_applicant"],
        "title_include_keywords": [],
        "title_exclude_keywords": [],
        "company_exclude": [],
        "auto_scoring_depth": "off",
    },
    {
        "name": "Jobright.ai",
        "active": False,
        "search_mode": "jobright",
        "sources": [],
        "title_include_keywords": [],
        "title_exclude_keywords": [],
        "company_exclude": [],
        "auto_scoring_depth": "off",
    },
]


MOCK_RESUME_JSON = {
    "header": {
        "name": "Alex Johnson",
        "contact_items": [
            {"text": "San Francisco, CA", "url": ""},
            {"text": "alex@example.com", "url": "mailto:alex@example.com"},
            {"text": "linkedin.com/in/alexjohnson", "url": "https://linkedin.com/in/alexjohnson"},
        ],
    },
    "summary": "Product manager with 8 years of experience building B2B SaaS products. Led cross-functional teams of 5-15 across 3 product lines, driving $12M ARR growth. Strong background in data-driven decision making, user research, and agile delivery.",
    "experience": [
        {
            "company": "TechCorp",
            "title": "Senior Product Manager",
            "location": "San Francisco, CA",
            "date": "2021 - Present",
            "bullets": [
                "Led product strategy for enterprise platform serving **2,000+ customers**, increasing NPS from 32 to 58",
                "Shipped AI-powered search feature that reduced time-to-resolution by **40%** across support workflows",
                "Managed $3M annual budget and prioritized roadmap across 3 engineering squads",
                "Drove adoption of experimentation framework, running **50+ A/B tests** per quarter",
            ],
        },
        {
            "company": "StartupXYZ",
            "title": "Product Manager",
            "location": "New York, NY",
            "date": "2018 - 2021",
            "bullets": [
                "Launched MVP marketplace product from 0 to **$2M ARR** in 18 months",
                "Defined and executed migration from monolith to microservices architecture",
                "Conducted **100+ user interviews** to inform product-market fit pivots",
                "Collaborated with design team to reduce onboarding drop-off by **35%**",
            ],
        },
        {
            "company": "BigFinance Inc.",
            "title": "Business Analyst",
            "location": "Chicago, IL",
            "date": "2016 - 2018",
            "bullets": [
                "Built dashboards and reporting tools for trading desk, saving **20 hours/week** of manual work",
                "Translated business requirements into technical specs for engineering team",
                "Led UAT for $5M regulatory compliance project delivered on schedule",
            ],
        },
    ],
    "skills": {
        "Product": "Roadmapping, A/B Testing, User Research, PRDs, OKRs, Agile/Scrum",
        "Technical": "SQL, Python, Jira, Amplitude, Mixpanel, Figma, REST APIs",
        "Domain": "B2B SaaS, Fintech, Marketplace, Enterprise, AI/ML Products",
    },
    "education": [
        {
            "school": "University of California, Berkeley",
            "location": "Berkeley, CA",
            "degree": "B.S. Computer Science, Minor in Business Administration",
        },
    ],
}

MOCK_CV_TEXT = """ALEX JOHNSON
San Francisco, CA | alex@example.com | linkedin.com/in/alexjohnson

SUMMARY
Product manager with 8 years of experience building B2B SaaS products. Led cross-functional teams of 5-15 across 3 product lines, driving $12M ARR growth. Strong background in data-driven decision making, user research, and agile delivery.

EXPERIENCE

Senior Product Manager | TechCorp | San Francisco, CA | 2021 - Present
- Led product strategy for enterprise platform serving 2,000+ customers, increasing NPS from 32 to 58
- Shipped AI-powered search feature that reduced time-to-resolution by 40% across support workflows
- Managed $3M annual budget and prioritized roadmap across 3 engineering squads
- Drove adoption of experimentation framework, running 50+ A/B tests per quarter

Product Manager | StartupXYZ | New York, NY | 2018 - 2021
- Launched MVP marketplace product from 0 to $2M ARR in 18 months
- Defined and executed migration from monolith to microservices architecture
- Conducted 100+ user interviews to inform product-market fit pivots
- Collaborated with design team to reduce onboarding drop-off by 35%

Business Analyst | BigFinance Inc. | Chicago, IL | 2016 - 2018
- Built dashboards and reporting tools for trading desk, saving 20 hours/week of manual work
- Translated business requirements into technical specs for engineering team
- Led UAT for $5M regulatory compliance project delivered on schedule

SKILLS
Product: Roadmapping, A/B Testing, User Research, PRDs, OKRs, Agile/Scrum
Technical: SQL, Python, Jira, Amplitude, Mixpanel, Figma, REST APIs
Domain: B2B SaaS, Fintech, Marketplace, Enterprise, AI/ML Products

EDUCATION
B.S. Computer Science, Minor in Business Administration
University of California, Berkeley
"""


def seed_searches(db):
    """Seed default searches if none exist (except LinkedIn Extension which is always ensured)."""
    existing_modes = {s.search_mode for s in db.query(Search).all()}
    for s in SEED_SEARCHES:
        if s["search_mode"] not in existing_modes:
            db.add(Search(**s))
    db.commit()


def seed_mock_cv(db):
    """Seed a mock CV and resume for demonstration. Sets it as default CV for all companies."""
    if db.query(CV).count() > 0:
        return  # User already has CVs

    # Create CV record (for scoring)
    cv = CV(
        version="Sample PM",
        filename="Sample_PM_Resume.pdf",
        pdf_data=b"%PDF-1.0 mock",  # Placeholder — real PDF generated from resume builder
        extracted_text=MOCK_CV_TEXT,
        page_count=1,
    )
    db.add(cv)
    db.flush()

    # Set as default CV
    default_row = db.query(Setting).filter(Setting.key == "default_cv_id").first()
    if default_row:
        default_row.value = str(cv.id)
    db.commit()

    # Pre-select this CV for all seeded companies
    for company in db.query(Company).all():
        company.selected_cv_ids = [str(cv.id)]
    db.commit()

    # Create matching resume (for resume builder)
    if db.query(Resume).count() == 0:
        resume = Resume(
            name="Sample PM",
            is_base=True,
            template="garamond_alt",
            page_format="letter",
            json_data=MOCK_RESUME_JSON,
        )
        db.add(resume)
        db.commit()

    logger.info("Seeded mock CV + resume 'Sample PM'")


def run_seeds():
    db = SessionLocal()
    try:
        run_migrations(db)
        seed_settings(db)
        seed_companies(db)
        seed_h1b_slugs(db)
        seed_searches(db)
        seed_mock_cv(db)
        cleanup_removed_settings(db)
    finally:
        db.close()
