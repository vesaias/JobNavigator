"""Seed settings and companies tables with defaults on first run."""
import logging
import json
import re
import secrets
from backend.models.db import SessionLocal, Setting, Company, Search, Resume
from backend.accounts.settings import install_row, put_setting
from sqlalchemy import text
from backend.analyzer.llm_client import LOCAL_LLM_URLS, REASONING_EFFORTS

logger = logging.getLogger("jobnavigator.seed")


DEFAULT_SETTINGS = {
    "fit_score_threshold": ("60", "Minimum fit score to trigger Telegram alert"),
    "scrape_interval_minutes": ("60", "How often the job checker runs"),
    "email_check_interval_minutes": ("30", "How often Gmail is polled"),
    "telegram_enabled": ("false", "Toggle all Telegram notifications on/off"),
    "digest_cron": ("0 8 * * *", "Daily digest cron (min hour day month dow). Empty = disabled"),
    "telegram_chat_id": ("", "Your Telegram chat ID"),
    "telegram_webhook_secret": ("", "Auto-generated secret token validated on every /api/telegram/webhook call. Rotate from the Telegram settings tab."),
    # MT-17: a member sends through the household bot (TELEGRAM_BOT_TOKEN) or its own bot.
    # The owner always uses the household bot; these two are read for members only.
    "telegram_bot_mode": ("household", "Telegram bot for this account: household (the owner's bot) or own"),
    "telegram_bot_token": ("", "This account's own Telegram bot token (used when telegram_bot_mode = own)"),
    "body_exclusion_phrases": (json.dumps([]), "JD phrases that flag exclusion (H-1B, language, etc.). Add phrases to auto-skip jobs containing them."),
    # weekday NAME, not a digit: APScheduler numbers 0 = Monday (vixie cron 0 = Sunday), so "0" fired Monday
    "h1b_cron": ("0 2 * * sun", "H-1B refresh cron (min hour day month dow). Empty = disabled"),
    "cleanup_cron": ("0 4 * * *", "Job cleanup cron (min hour day month dow). Empty = disabled"),
    "job_archive_after_days": ("90", "Delete skipped jobs older than N days (used by cleanup job)"),
    "auto_reject_after_days": ("0", "Reject applications older than N days, 0 = disabled (used by reject job)"),
    "proxy_url": ("", "Optional rotating proxy for scraping"),
    "dashboard_api_key": ("", "Dashboard password — changeable from dashboard"),
    "default_resume_id": ("", "Default base Resume ID used for scoring when no company-level Resumes are configured"),
    "company_exclude_global": (json.dumps([]), "Global company ignore list — applies to all searches"),
    "title_exclude_global": (json.dumps([]), "Global title exclude keywords — applies to all searches and companies"),
    "linkedin_email": ("", "LinkedIn account email for personal scrape mode"),
    "linkedin_password": ("", "LinkedIn account password for personal scrape mode"),
    "linkedin_mock_email": ("", "LinkedIn mock account email for Extension Voyager API"),
    "linkedin_mock_password": ("", "LinkedIn mock account password for Extension Voyager API"),
    "jobright_email": ("", "Jobright.ai account email"),
    "jobright_password": ("", "Jobright.ai account password"),
    "jobright_session_id": ("", "Jobright.ai session cookie (auto-managed, 60-day expiry)"),
    # The cookie itself is write-only to the UI (redacted on GET), so the
    # Accounts tab needs a plain timestamp to say how long it is still good for.
    "jobright_session_obtained_at": ("", "UTC ISO timestamp of the last successful Jobright login. Read-only; set by the scraper."),
    # Billed per result by Apify; `_api_key` suffix keeps it redacted on GET /settings.
    "apify_api_key": ("", "Apify API token for the Apify search mode"),
    "reject_cron": ("0 4 * * *", "Auto-reject cron (min hour day month dow). Empty = disabled"),
    "dedup_copy_link": ("ignored", "A copy of a posting under another link in the same city: ignored or new"),
    "dedup_copy_city": ("ignored", "A copy of a posting or role in another city: ignored or new"),
    "dedup_copy_repost": ("ignored", "The same role reposted under a new id in the same city: ignored or new"),
    # telemetry/level.py: the owner's choice, empty until asked (JN_TELEMETRY overrides it)
    "telemetry_level": ("", "Telemetry: full (Yes) or essentials; empty = not asked yet"),
    "backup_cron": ("0 3 * * *", "Backup cron schedule (min hour day month dow). Empty = disabled"),
    "scoring_rubric": ("Score each resume using these criteria (each 0-20, sum to 0-100):\n1. SKILLS MATCH (weight: 20): How many required technical skills/tools does the candidate have?\n2. EXPERIENCE LEVEL (weight: 20): Does seniority/years match? (entry-level resume for senior role = low)\n3. DOMAIN FIT (weight: 20): Has the candidate worked in the same industry/domain?\n4. ROLE ALIGNMENT (weight: 20): Does the candidate's career trajectory match this role type?\n5. REQUIREMENTS MET (weight: 20): Does the candidate meet stated requirements (education, certs, clearance)?\n\nUse the FULL 0-100 range. 90+ = perfect match. 50-70 = decent with gaps. Below 30 = poor match.\nAvoid clustering scores — differentiate meaningfully between resumes and jobs.", "Editable resume scoring rubric"),
    "scoring_output_light": ('Return ONLY this JSON:\n{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "best_cv": "CV_NAME"\n}', "Light scoring output schema"),
    "scoring_output_full": ('Return ONLY this JSON:\n{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "best_cv": "CV_NAME",\n  "breakdown": {"skills": 0-20, "experience": 0-20, "domain": 0-20, "role": 0-20, "requirements": 0-20},\n  "summary": "2-3 sentence assessment of candidate-job fit",\n  "requirement_mapping": [\n    {"requirement": "JD requirement text", "cv_match": "matching CV line or null", "matched": true/false, "severity": "required or preferred"}\n  ],\n  "keyword_coverage_pct": 0-100,\n  "matched_keywords": ["keyword1", "keyword2"],\n  "missing_keywords": ["keyword3", "keyword4"],\n  "hard_blockers": ["blocker if any"],\n  "ats_tip": "one actionable ATS optimization suggestion"\n}', "Full scoring output schema with keyword analysis"),
    "llm_provider": ("claude_api", "LLM provider: claude_api, claude_code, codex_cli, antigravity_cli, opencode_go, openai, ollama, lmstudio, openrouter, cheaper_inference"),
    "llm_model": ("claude-sonnet-5", "LLM model name"),
    "llm_effort": ("", "Reasoning effort for the Primary model (empty = the model's default; values depend on the provider)"),
    # One key per provider (3.1): every model slot on that provider uses it. Empty = the env var of
    # the same name in upper case, for the owner and members on 'inherit' (never a member on 'own').
    "anthropic_api_key": ("", "Claude API key, used by every model slot on Claude API (empty = ANTHROPIC_API_KEY from .env)"),
    "openai_api_key": ("", "OpenAI API key, used by every model slot on OpenAI (empty = OPENAI_API_KEY from .env)"),
    "openrouter_api_key": ("", "OpenRouter API key, used by every model slot on OpenRouter (empty = OPENROUTER_API_KEY from .env)"),
    "opencode_api_key": ("", "OpenCode Go API key, used by every model slot on OpenCode Go (empty = OPENCODE_API_KEY from .env)"),
    "cheaper_inference_api_key": ("", "Cheaper Inference API key, used by every model slot on Cheaper Inference (empty = CHEAPER_INFERENCE_API_KEY from .env)"),
    "claude_code_oauth_token": ("", "Claude Code subscription token from `claude setup-token` (empty = CLAUDE_CODE_OAUTH_TOKEN from .env; a member with its own Models section can set its own)"),
    # Owner-only (section llm_local): the host's local model servers. Seeded empty, so the address
    # is read at call time from LMSTUDIO_BASE_URL / OLLAMA_BASE_URL, else the built-in default (L-03:
    # a seeded env value froze .env at first boot, and /settings/defaults served it to members).
    "lmstudio_base_url": ("", "LM Studio server address (OpenAI-compatible, ends in /v1). Empty = LMSTUDIO_BASE_URL from .env, else http://localhost:1234/v1. From Docker use http://host.docker.internal:1234/v1"),
    "ollama_base_url": ("", "Ollama server address. Empty = OLLAMA_BASE_URL from .env, else http://localhost:11434. From Docker use http://host.docker.internal:11434"),
    "llm_fallback_provider": ("", "Fallback LLM provider (empty = no fallback)"),
    "llm_fallback_model": ("", "Fallback model name"),
    "llm_fallback_effort": ("", "Reasoning effort for the fallback model (empty = the model's default; values depend on the provider)"),
    "scoring_llm_provider": ("", "Resume scoring provider override (empty = use Primary)"),
    "scoring_llm_model": ("", "Resume scoring model override (empty = use Primary)"),
    "scoring_llm_effort": ("", "Reasoning effort for the scoring override (empty = the Primary's on the same provider, else the model's default)"),
    "llm_models_list": (json.dumps([
        {"provider": "claude_api", "model": "claude-sonnet-5"},
        {"provider": "claude_api", "model": "claude-sonnet-4-6"},
        {"provider": "claude_api", "model": "claude-opus-5-5"},
        {"provider": "claude_api", "model": "claude-opus-5"},
        {"provider": "claude_api", "model": "claude-opus-4-8"},
        {"provider": "claude_api", "model": "claude-opus-4-7"},
        {"provider": "claude_api", "model": "claude-opus-4-6"},
        {"provider": "claude_api", "model": "claude-haiku-4-5"},
        {"provider": "claude_api", "model": "claude-fable-5-1"},
        {"provider": "claude_api", "model": "claude-fable-5"},
        {"provider": "claude_code", "model": "claude-sonnet-5"},
        {"provider": "claude_code", "model": "claude-sonnet-4-6"},
        {"provider": "claude_code", "model": "claude-opus-5-5"},
        {"provider": "claude_code", "model": "claude-opus-5"},
        {"provider": "claude_code", "model": "claude-opus-4-8"},
        {"provider": "claude_code", "model": "claude-opus-4-7"},
        {"provider": "claude_code", "model": "claude-opus-4-6"},
        {"provider": "claude_code", "model": "claude-haiku-4-5"},
        {"provider": "claude_code", "model": "claude-fable-5-1"},
        {"provider": "claude_code", "model": "claude-fable-5"},
        {"provider": "codex_cli", "model": "gpt-6-astra"},
        {"provider": "codex_cli", "model": "gpt-6-sol"},
        {"provider": "codex_cli", "model": "gpt-6-luna"},
        {"provider": "codex_cli", "model": "gpt-5.6-sol"},
        {"provider": "codex_cli", "model": "gpt-5.6-terra"},
        {"provider": "codex_cli", "model": "gpt-5.6-luna"},
        {"provider": "codex_cli", "model": "gpt-5.5"},
        # Antigravity CLI — Google subscription. Slugs carry the reasoning effort;
        # `agy models` is the live catalog and it also serves non-Google models.
        {"provider": "antigravity_cli", "model": "gemini-3.8-flash-high"},
        {"provider": "antigravity_cli", "model": "gemini-3.8-flash-medium"},
        {"provider": "antigravity_cli", "model": "gemini-3.8-flash-low"},
        {"provider": "antigravity_cli", "model": "gemini-3.7-flash-medium"},
        {"provider": "antigravity_cli", "model": "gemini-3.6-flash-medium"},
        {"provider": "antigravity_cli", "model": "gemini-3.1-pro-high"},
        {"provider": "antigravity_cli", "model": "gemini-3.1-pro-low"},
        {"provider": "antigravity_cli", "model": "claude-sonnet-4-6"},
        {"provider": "antigravity_cli", "model": "claude-opus-4-6-thinking"},
        {"provider": "antigravity_cli", "model": "gpt-oss-120b-medium"},
        {"provider": "openai", "model": "gpt-6-astra"},
        {"provider": "openai", "model": "gpt-6-sol"},
        {"provider": "openai", "model": "gpt-6-luna"},
        {"provider": "openai", "model": "gpt-5.6-sol"},
        {"provider": "openai", "model": "gpt-5.6-terra"},
        {"provider": "openai", "model": "gpt-5.6-luna"},
        {"provider": "openai", "model": "gpt-5.5"},
        {"provider": "openai", "model": "gpt-5.4"},
        {"provider": "openai", "model": "gpt-5.4-mini"},
        {"provider": "openai", "model": "gpt-5.4-nano"},
        {"provider": "openai", "model": "gpt-5.2"},
        {"provider": "openai", "model": "gpt-4o"},
        {"provider": "openai", "model": "gpt-4o-mini"},
        {"provider": "openai", "model": "o3"},
        {"provider": "ollama", "model": "llama3.3:70b"},
        {"provider": "ollama", "model": "llama3.1:8b"},
        {"provider": "ollama", "model": "qwen2.5:32b"},
        {"provider": "ollama", "model": "qwen2.5-coder:7b"},
        {"provider": "ollama", "model": "deepseek-r1:14b"},
        {"provider": "ollama", "model": "mistral:7b"},
        {"provider": "ollama", "model": "gemma2:9b"},
        {"provider": "ollama", "model": "phi3:14b"},
        # OpenCode Go (subscription) — models that answer on /chat/completions; the model id is
        # bare, not the CLI's `opencode-go/` alias. A Go API key is required. A model Go serves on
        # another protocol fails with a readable "another protocol" error, not a retry.
        {"provider": "opencode_go", "model": "glm-5.3"},
        {"provider": "opencode_go", "model": "glm-5.3-flash"},
        {"provider": "opencode_go", "model": "glm-5.2"},
        {"provider": "opencode_go", "model": "kimi-k3"},
        {"provider": "opencode_go", "model": "kimi-k2.7-code"},
        {"provider": "opencode_go", "model": "kimi-k2.6"},
        {"provider": "opencode_go", "model": "deepseek-v4.1-flash"},
        {"provider": "opencode_go", "model": "deepseek-v4-pro"},
        {"provider": "opencode_go", "model": "deepseek-v4-flash"},
        {"provider": "opencode_go", "model": "mimo-v2.6-pro"},
        {"provider": "opencode_go", "model": "mimo-v2.6-flash"},
        {"provider": "opencode_go", "model": "mimo-v2.5"},
        {"provider": "opencode_go", "model": "mimo-v2.5-pro"},
        {"provider": "opencode_go", "model": "longcat-2.0"},
        {"provider": "opencode_go", "model": "hy3"},
        {"provider": "opencode_go", "model": "minimax-m3"},
        {"provider": "opencode_go", "model": "qwen3.8-max"},
        {"provider": "opencode_go", "model": "qwen3.8-flash"},
        # OpenRouter — one key reaches every vendor; slugs are vendor-prefixed.
        # A popular starter set; the full ~420 are fetchable in Settings via the API.
        {"provider": "openrouter", "model": "anthropic/claude-fable-5.1"},
        {"provider": "openrouter", "model": "anthropic/claude-opus-5.5"},
        {"provider": "openrouter", "model": "anthropic/claude-opus-5"},
        {"provider": "openrouter", "model": "anthropic/claude-sonnet-5"},
        {"provider": "openrouter", "model": "openai/gpt-6-sol"},
        {"provider": "openrouter", "model": "openai/gpt-6-luna"},
        {"provider": "openrouter", "model": "openai/gpt-5.6-luna"},
        {"provider": "openrouter", "model": "openai/o3-pro"},
        {"provider": "openrouter", "model": "google/gemini-3.8-flash"},
        {"provider": "openrouter", "model": "google/gemini-3.1-pro-preview"},
        {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
        {"provider": "openrouter", "model": "deepseek/deepseek-v3.2"},
        {"provider": "openrouter", "model": "meta-llama/llama-4-maverick"},
        {"provider": "openrouter", "model": "x-ai/grok-4.6"},
        {"provider": "openrouter", "model": "mistralai/mistral-large-2512"},
        # Cheaper Inference — one key reaches models from several labs; ids are bare. A starter set;
        # the full catalog is searchable in Settings (public /models list, chat models only).
        {"provider": "cheaper_inference", "model": "gpt-5.4-mini"},
        {"provider": "cheaper_inference", "model": "gpt-5.4"},
        {"provider": "cheaper_inference", "model": "claude-sonnet-5"},
        {"provider": "cheaper_inference", "model": "deepseek-v4-flash"},
        {"provider": "cheaper_inference", "model": "glm-5.3"},
    ]), "Known LLM models per provider (JSON array, user can add custom entries)"),
    "scoring_max_concurrent": ("5", "Max parallel scoring jobs (others queue until a slot opens)"),
    "tailoring_max_concurrent": ("2", "Max concurrent resume-tailoring LLM calls"),
    "scrape_max_concurrent": ("1", "Scrapes at once, 1 or 2: Run all, one company, one search and the scheduled scrape; others wait their turn"),
    "tailor_auto_quick_score": ("light", "After tailoring finishes, auto-launch a score chain. Values: 'off' | 'light' | 'full'. Default 'light'. Legacy 'true'='light', 'false'='off'."),
    "prompt_caching_enabled": ("true", "Use Anthropic prompt caching on resume scoring (claude_api only; ~50% cheaper input tokens on same-batch calls). Set false to disable as a rollback lever."),
    "scoring_default_depth": ("light", "Default scoring depth: light or full"),
    # Dashboard-only switch: the Jobs pane reads it, nothing on the backend does.
    # The zoom LEVEL itself is per-browser (localStorage), never a setting.
    "feed_zoom_floater": ("true", "Show the + / - zoom control on postings in the Jobs pane"),
    "on_save_action": ("off", "Action when job is saved: off, light, or full"),
    "email_llm_enabled": ("false", "Enable LLM second pass for ambiguous email classification"),
    "email_llm_provider": ("", "LLM provider for email classification (empty = use primary llm_provider)"),
    "email_llm_model": ("", "LLM model for email classification (empty = use primary llm_model)"),
    "email_llm_effort": ("", "Reasoning effort for email classification (empty = the Primary's on the same provider, else the model's default)"),
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
    "cv_tailor_llm_provider": ("", "LLM provider for resume tailoring (empty = use primary llm_provider)"),
    "cv_tailor_llm_model": ("", "LLM model for resume tailoring (empty = use primary llm_model)"),
    "cv_tailor_llm_effort": ("", "Reasoning effort for resume tailoring (empty = the Primary's on the same provider, else the model's default)"),
    "cv_tailor_prompt": ("Tailor this resume for the job description below.\n\nRules for MAIN bullets[]:\n- Rewrite the summary to target this specific role\n- For each experience bullet: if it benefits from JD keyword alignment, reformulate it. If it's already well-suited, leave it UNCHANGED\n- Keep the same number of bullets per experience entry - do not add or remove\n- Reorder skills to prioritize JD-relevant ones first\n- Do NOT invent new experience, skills, or facts in the main bullets. If something is missing, map to the closest truthful concept\n- NEVER add skills the candidate does not have\n- Preserve all company names, titles, dates, locations, education exactly\n- Do NOT use em-dashes or unicode special characters. Use regular hyphens (-) and ASCII only\n- Preserve **bold** formatting (double asterisks) from the original bullets. For reformulated bullets, wrap the strongest metric or achievement in **bold** (e.g. **40,000+ new clients**, **reduced error rates by 30%**). Each bullet should have at most one bold highlight\n- VERIFICATION: every reformulated bullet must trace to the original resume. If you cannot trace it, leave the original unchanged.\n\nRules for suggested_bullets[] (gap-fillers - DIFFERENT from main bullets):\n- For each experience entry, generate 1-2 PLAUSIBLE STAR-format bullets that cover JD keywords/skills no existing bullet in this role covers\n- These MAY invent realistic, believable facts/metrics that someone in this role/title at this company at this seniority would credibly have done\n- Specifically target keywords from the JD that no existing bullet mentions\n- Use STAR format: strong action verb, context, concrete (possibly invented) metric or outcome\n- The user reviews these in a diff modal and accepts/rejects each - they know suggestions are speculative gap-fillers\n- Wrap the strongest metric in **bold** (one per bullet)\n- Skip a role entirely if no JD keyword gap exists for it\n\nResume:\n{resume_json}\n\nJob Description:\n{job_description}\n\nReturn ONLY this JSON:\n{\"summary\": \"rewritten summary\", \"experience\": [{\"company\": \"unchanged\", \"title\": \"unchanged\", \"location\": \"unchanged\", \"date\": \"unchanged\", \"description\": \"unchanged or null\", \"bullets\": [\"reformulated or unchanged bullet from existing content\"], \"suggested_bullets\": [\"plausible gap-filler covering missing JD keyword\"]}], \"skills\": {\"reordered label\": \"reordered value\"}}", "Editable resume tailoring LLM prompt template"),
    "persona_tailor_prompt": ("Tailor a FOCUSED resume from this rich candidate profile, targeted at the job description below.\n\nThe candidate profile is a deep pool - most roles have many bullets. SELECT only the strongest aligned with the JD; drop the rest.\n\nRules for MAIN bullets[]:\n- Rewrite the summary to target this specific role (2-4 sentences, lead with the most relevant strength)\n- For each experience entry: SELECT only 3-5 bullets (max 6 for the most senior/recent role) that best match JD keywords and required skills\n- Reformulate each selected bullet to use the JD's exact vocabulary where possible\n- Reorder skills to prioritize JD-relevant ones first; cap at 6 categories\n- Do NOT invent new experience, skills, or facts in the main bullets. Only reframe existing content from the candidate profile\n- NEVER add skills the candidate does not have\n- Preserve all company names, titles, dates, locations, education exactly\n- Do NOT use em-dashes or unicode special characters. Use regular hyphens (-) and ASCII only\n- Preserve **bold** formatting. For reformulated bullets, wrap the strongest metric in **bold** (one per bullet)\n- VERIFICATION: every selected/reformulated bullet must be traceable to the candidate profile\n\nRules for suggested_bullets[] (gap-fillers - DIFFERENT from main bullets):\n- For each experience entry, generate 1-2 PLAUSIBLE STAR-format bullets that cover JD keywords/skills no main bullet (selected from the pool) covers\n- These MAY invent realistic, believable facts/metrics that someone in this role at this company at this seniority would credibly have done\n- Specifically target JD keywords that no main bullet mentions\n- STAR format: strong action verb, context, concrete (possibly invented) metric or outcome\n- The user reviews these in a diff modal and accepts/rejects each\n- Wrap the strongest metric in **bold** (one per bullet)\n- Skip a role if no JD keyword gap exists\n\nCandidate Profile:\n{resume_json}\n\nJob Description:\n{job_description}\n\nReturn ONLY this JSON:\n{\"summary\": \"rewritten summary\", \"experience\": [{\"company\": \"unchanged\", \"title\": \"unchanged\", \"location\": \"unchanged\", \"date\": \"unchanged\", \"description\": \"unchanged or null\", \"bullets\": [\"selected + reformulated bullet from candidate profile\"], \"suggested_bullets\": [\"plausible gap-filler covering missing JD keyword\"]}], \"skills\": {\"reordered label\": \"reordered value\"}}", "Editable Persona tailoring LLM prompt template - used when base_resume_id='persona' to constrain bullet selection from the rich pool"),
    "cover_letter_llm_provider": ("", "LLM provider for cover-letter generation (empty = use primary llm_provider)"),
    "cover_letter_llm_model": ("", "LLM model for cover-letter generation (empty = use primary llm_model)"),
    "cover_letter_llm_effort": ("", "Reasoning effort for cover-letter generation (empty = the Primary's on the same provider, else the model's default)"),
    "cover_letter_prompt": ("Write a cover letter for the candidate, targeting the job described below.\n\nGround everything in the candidate's resume (provided above) and the persona preferences. Do NOT invent experience, employers, titles, metrics, or skills the resume does not contain. Pull concrete achievements from the resume; reframe them toward what the job needs.\n\nStructure:\n- A short greeting line (use the recipient/company if known, else a neutral 'Dear Hiring Team,').\n- 3 body paragraphs: (1) a hook that connects the candidate to this specific role/company, (2) the strongest 2-3 proof points from the resume mapped to the job's needs, (3) a brief close on motivation/fit and a call to talk.\n- A closing line ('Sincerely,') and the candidate's name as signature.\n\nStyle:\n- {voice_instruction}\n- Length: {length_instruction}\n- First person. No corporate cliches, no 'I am writing to apply'. No em-dashes or unicode; ASCII only. Do NOT fabricate.\n\nJob:\n{job_description}\n\nReturn ONLY this JSON:\n{\"greeting\": \"Dear ...,\", \"body_paragraphs\": [\"...\", \"...\", \"...\"], \"closing\": \"Sincerely,\", \"signature\": \"Candidate Name\"}", "Editable cover-letter generation LLM prompt. Placeholders: {voice_instruction}, {length_instruction}, {job_description}."),
    "cover_letter_voice_presets": (json.dumps([
        {"id": "professional", "label": "Professional & direct", "instruction": "Concise, concrete, results-first. No corporate filler or cliches."},
        {"id": "warm", "label": "Warm & personable", "instruction": "First-person, genuine enthusiasm, conversational but polished."},
        {"id": "formal", "label": "Formal & traditional", "instruction": "Classic business-letter register, measured and respectful."},
        {"id": "confident", "label": "Confident & bold", "instruction": "Lead with strong claims and leadership framing; assertive but not arrogant."},
        {"id": "storytelling", "label": "Storytelling", "instruction": "Open with a brief hook or narrative, then connect it to the role."},
    ]), "Editable cover-letter voice presets: list of {id, label, instruction}. The selected preset's instruction is injected into the generation prompt."),
    "cover_letter_default_voice": ("professional", "Default voice preset id for new cover letters (must match an id in cover_letter_voice_presets)"),
    "autofill_field_patterns": (json.dumps({
        "gender": ["gender", "what is your gender", "gender identity"],
        "race_ethnicity": ["race", "ethnicity", "race/ethnicity", "racial background", "ethnicities"],
        "veteran_status": ["veteran", "protected veteran", "vevraa"],
        "hispanic_latino": ["hispanic or latino", "hispanic/latino", "are you hispanic", "hispanic latino"],
        "disability_status": ["disability", "disabled", "section 503"],
        "age_range": ["current age", "your age", "age range", "how old", "what is your age"],
        "transgender": ["transgender", "identify as transgender", "trans"],
        "sexual_orientation": ["sexual orientation", "your sexual orientation", "how do you identify your sexual"],
        "authorized_us": ["authorized to work", "legally authorized", "work authorization"],
        "requires_sponsorship_now": ["require sponsorship", "need sponsorship", "visa sponsorship", "require immigration", "immigration sponsorship"],
        "requires_sponsorship_future": ["future sponsorship", "sponsorship in the future"],
        "over_18": ["over 18", "at least 18", "18 years of age"],
        "first_name": ["first name", "given name"],
        "last_name": ["last name", "surname", "family name"],
        "full_name": ["full name", "your name", "legal name"],
        "email": ["email"],
        "phone": ["phone", "mobile", "telephone"],
        "city": ["city", "current location", "location"],
        "state": ["state", "province"],
        "country": ["country"],
        "linkedin": ["linkedin"],
        "github": ["github"],
        "portfolio": ["portfolio", "personal website", "website"],
        "current_company": ["current company", "current employer"],
        "willing_to_relocate": ["relocate", "willing to relocate"],
        "willing_remote": ["work remotely", "remote work"],
        "desired_salary": ["desired salary", "salary expectation", "expected salary", "compensation expectation"],
        "notice_period": ["notice period"],
        "earliest_start": ["start date", "available to start", "earliest start"],
        "referral_source": ["referral source", "referred by"],
        "how_did_you_hear": ["how did you hear"],
    }), "Editable dictionary: canonical autofill key -> list of label synonyms used to match a form field to an answer"),
    "autofill_option_synonyms": (json.dumps({
        "veteran_status": {
            "protected_veteran": ["i am a protected veteran", "identify as one or more", "yes"],
            "not_protected_veteran": ["not a protected veteran", "not a veteran", "no"],
            "decline": ["decline", "don't wish to answer", "do not wish to answer", "prefer not"],
        },
        "hispanic_latino": {
            "yes": ["hispanic or latino", "yes, i am", "yes"],
            "no": ["not hispanic or latino", "no, i am not", "no"],
            "decline": ["decline", "don't wish to answer", "prefer not"],
        },
        "disability_status": {
            "yes": ["yes, i have a disability", "yes", "i have a disability"],
            "no": ["no, i don't have a disability", "no", "do not have a disability"],
            "decline": ["decline", "do not want to answer", "prefer not"],
        },
        "gender": {
            "male": ["male", "man"],
            "female": ["female", "woman"],
            "nonbinary": ["non-binary", "nonbinary", "other"],
            "decline": ["decline", "prefer not", "don't wish"],
        },
        "race_ethnicity": {
            "hispanic_latino": ["hispanic", "latino", "latinx"],
            "white": ["white"],
            "black": ["black", "african american"],
            "asian": ["asian"],
            "native_american": ["native american", "alaska native", "american indian"],
            "pacific_islander": ["pacific islander", "native hawaiian"],
            "two_or_more": ["two or more"],
            "decline": ["decline", "prefer not", "don't wish"],
        },
        "work_auth_type": {
            "citizen": ["u.s. citizen", "us citizen", "citizen"],
            "permanent_resident": ["permanent resident", "green card"],
            "visa": ["visa", "work visa"],
            "other": ["other"],
        },
        "age_range": {
            "under_30": ["under 30", "under 30 years", "less than 30"],
            "30_39": ["30-39", "30 - 39", "30 to 39"],
            "40_49": ["40-49", "40 - 49", "40 to 49"],
            "50_59": ["50-59", "50 - 59", "50 to 59"],
            "60_plus": ["60 or older", "60+", "60 and over", "over 60"],
            "decline": ["prefer not to answer", "decline", "don't wish", "do not wish"],
        },
        "transgender": {
            "yes": ["yes"],
            "no": ["no"],
            "decline": ["prefer not to answer", "decline", "don't wish", "do not wish"],
        },
        "sexual_orientation": {
            "heterosexual": ["heterosexual", "straight"],
            "gay": ["gay"],
            "lesbian": ["lesbian"],
            "bisexual": ["bisexual"],
            "queer": ["queer"],
            "other": ["other"],
            "decline": ["prefer not to answer", "decline", "don't wish", "do not wish"],
        },
        "_bool": {
            "true": ["yes", "true"],
            "false": ["no", "false"],
        },
    }), "Editable dictionary: enum key -> {enum value -> list of option-text synonyms}; '_bool' maps yes/no. Used to pick the right option on a form."),
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
        # "jk" deliberately absent — it is Indeed's job identity, and stripping
        # it collapsed every Indeed posting onto one external_id.
        # Search-context noise (career page filters that leak into job hrefs):
        "categories", "cities", "locations", "departments", "teams", "regions", "country", "category",
    ]), "URL query params stripped before dedup hashing — tracking/referral noise"),
    "autofill_llm_provider": ("", "LLM provider for application autofill (empty = use primary llm_provider)"),
    "autofill_llm_model": ("", "LLM model for application autofill (empty = use primary llm_model)"),
    "autofill_llm_effort": ("", "Reasoning effort for application autofill (empty = the Primary's on the same provider, else the model's default)"),
    "autofill_default_length": ("250", "Default target character length for autofill answers when a field has no maxlength"),
    "autofill_prompt": (
        "You are the candidate, writing a short first-person answer to a job-application question.\n\n"
        "Use ONLY facts from the candidate profile and the reusable Q&A bank below. Never invent employers, "
        "titles, metrics, or skills. If the Q&A bank already answers this (or a close variant), adapt that answer "
        "to this company and role instead of writing from scratch.\n\n"
        "Write like a real person: specific, direct, plain. No corporate filler or buzzwords (no 'leverage', "
        "'passionate', 'excited to', 'thrilled', 'synergy', 'mission-driven'), no generic mission-statement lines, "
        "no restating the question. ASCII only, no em-dashes. Keep it at or under {max_chars} characters.\n\n"
        "Put the finished answer (first person, no preamble, no meta-commentary) inside the JSON below, and put "
        "NOTHING outside it — no reasoning, no notes about the profile, no 'I'll write...' lines.\n\n"
        "CANDIDATE PROFILE:\n{persona}\n\n"
        "Q&A BANK (reusable prior answers):\n{qa_bank}\n\n"
        "TARGET: {company} - {position}\n"
        "QUESTION: {question}\n\n"
        "Return ONLY this JSON:\n{\"answer\": \"...\"}",
        "Editable application-autofill LLM prompt. Placeholders: {persona}, {qa_bank}, {company}, {position}, {question}, {max_chars}."
    ),
    "prep_include": ("resume,posting,notes",
        "Sections the interview prep handover includes by default (comma-separated: resume, posting, notes)"),
    "prep_ask": (
        "Prepare me for this interview. Ground every answer in my resume above — use my real projects, "
        "employers and numbers, and invent nothing.\n\n"
        "1. The 10 questions this panel is most likely to ask, ordered by likelihood, with a short answer for each.\n"
        "2. Every requirement in the posting I do not clearly meet, the honest framing to use, and the closest "
        "adjacent experience I can point to.\n"
        "3. Two or three stories from my background worth rehearsing, in STAR form.\n"
        "4. The questions I should ask them that show I read this posting closely.\n"
        "5. Anything in my resume that is a liability for this role, and how to handle it if raised.",
        "The closing 'What I need from you' section of the interview prep handover (Applications → Generate prep handover for AI)."
    ),
}

# Settings the app writes at runtime but never seeds. PATCH /api/settings rejects
# keys outside DEFAULT_SETTINGS, so these have to be listed explicitly.
RUNTIME_SETTING_KEYS = {
    "gmail_processed_ids",   # email_monitor/gmail_client.py — processed-message dedup
    "gmail_refresh_token",   # Gmail OAuth setup (gmail_oauth_setup.py)
    "llm_seeded_models",     # migrate_llm_settings() — one-time "defaults offered" marker
}


def is_known_setting(key: str) -> bool:
    """True if PATCH /api/settings may write this key."""
    return key in DEFAULT_SETTINGS or key in RUNTIME_SETTING_KEYS


def unknown_setting_keys(keys) -> list:
    """The subset of `keys` no reader in the codebase would ever look at."""
    return [k for k in keys if not is_known_setting(k)]


# ── Value validation ─────────────────────────────────────────────────────────
# The value shapes the app actually parses (int, cron, enum) are validated here,
# so an unparseable value can't reach configure_scheduler() and crash the backend.

def _int_setting_keys() -> set:
    """Every seeded key whose default is a plain integer, derived (not listed) so a new numeric default automatically picks up the guard."""
    keys = set()
    for key, (value, _desc) in DEFAULT_SETTINGS.items():
        if not isinstance(value, str):
            continue
        try:
            int(value)
        except (TypeError, ValueError):
            continue
        keys.add(key)
    return keys


INT_SETTING_KEYS = _int_setting_keys()

# Providers the LLM dispatcher knows how to call. "" means "inherit the primary
# llm_provider", which every per-feature prefix does.
_LLM_PROVIDERS = {"", "claude_api", "claude_code", "codex_cli", "antigravity_cli", "opencode_go", "openai", "ollama", "lmstudio", "openrouter",
                  "cheaper_inference"}

# Depth words. `tailor_auto_quick_score` also honours legacy boolean spellings
# (see routes_resumes._resolve_chain_score_depth).
_DEPTHS = {"light", "full"}

# Every effort any provider takes; llm_client drops a value the chosen provider lacks.
_EFFORTS = {""} | {e for values in REASONING_EFFORTS.values() for e in values}

ENUM_SETTING_VALUES = {
    "llm_provider": _LLM_PROVIDERS,
    "llm_fallback_provider": _LLM_PROVIDERS,
    "scoring_llm_provider": _LLM_PROVIDERS,
    "email_llm_provider": _LLM_PROVIDERS,
    "cv_tailor_llm_provider": _LLM_PROVIDERS,
    "cover_letter_llm_provider": _LLM_PROVIDERS,
    "autofill_llm_provider": _LLM_PROVIDERS,
    "llm_effort": _EFFORTS,
    "llm_fallback_effort": _EFFORTS,
    "scoring_llm_effort": _EFFORTS,
    "email_llm_effort": _EFFORTS,
    "cv_tailor_llm_effort": _EFFORTS,
    "cover_letter_llm_effort": _EFFORTS,
    "autofill_llm_effort": _EFFORTS,
    "scoring_default_depth": _DEPTHS,
    "on_save_action": {"off"} | _DEPTHS,
    "tailor_auto_quick_score": {"off", "false", "no", "0", "true", "yes", "1", ""} | _DEPTHS,
    "tracer_links_url_style": {"path", "param", "path_jobid", "param_jobid"},
    "telegram_bot_mode": {"household", "own"},
    "telemetry_level": {"", "full", "essentials"},   # "" = not asked yet (asked again)
}


LOCAL_URL_SETTING_KEYS = {key for key, _env, _default in LOCAL_LLM_URLS.values()}


def _cron_error(value: str) -> str | None:
    """None if `value` is a usable 5-field cron expression (empty = disabled)."""
    expr = (value or "").strip()
    if not expr:
        return None                      # empty disables the job — always allowed
    if len(expr.split()) != 5:
        return "needs exactly 5 whitespace-separated fields (min hour day month dow)"
    try:
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:                  # pragma: no cover - apscheduler always present in the app
        return None
    try:
        CronTrigger.from_crontab(expr)
    except (ValueError, KeyError) as e:
        return f"not a valid cron expression ({e})"
    return None


def invalid_setting_values(updates: dict) -> list:
    """Human-readable complaints for every value the app could not parse back, one entry per offending key so PATCH can reject the whole request at once."""
    problems = []
    for key, value in sorted(updates.items()):
        if key in INT_SETTING_KEYS:
            ok = False
            if isinstance(value, bool):
                ok = False               # True/False are ints in Python; not here
            elif isinstance(value, int):
                ok = True
            elif isinstance(value, str):
                try:
                    int(value.strip())
                    ok = True
                except (TypeError, ValueError):
                    ok = False
            if not ok:
                problems.append(f"{key}: must be a whole number (got {value!r})")
            elif int(str(value).strip()) < 0:
                problems.append(f"{key}: must not be negative (got {value!r})")
            continue
        if key.endswith("_cron"):
            if not isinstance(value, str):
                problems.append(f"{key}: must be a cron string (got {value!r})")
                continue
            err = _cron_error(value)
            if err:
                problems.append(f"{key}: {err}")
            continue
        if key in LOCAL_URL_SETTING_KEYS:
            v = value.strip() if isinstance(value, str) else None
            if v is None or (v and not re.match(r"^https?://[^\s/]+", v, re.I)):
                problems.append(f"{key}: must be an http:// or https:// address, or empty (got {value!r})")
            continue
        allowed = ENUM_SETTING_VALUES.get(key)
        if allowed is not None:
            if not isinstance(value, str) or value.strip().lower() not in allowed:
                shown = ", ".join(sorted(v for v in allowed if v)) or "(empty)"
                problems.append(f"{key}: must be one of {shown} (got {value!r})")
    return problems


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
    existing = {s.key for s in db.query(Setting).filter(Setting.account_id.is_(None)).all()}
    for key, (value, desc) in DEFAULT_SETTINGS.items():
        if key not in existing:
            db.add(Setting(key=key, value=value, description=desc))
    db.commit()
    # One-shot: seeded empty above so the row is visible in /api/settings; the
    # real cryptographically random value is generated here on first run.
    row = install_row(db, "telegram_webhook_secret")
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


def run_migration_statements(db, statements) -> list:
    """Execute each statement in its own SAVEPOINT and return the ones that failed.

    Postgres aborts the *whole* transaction on any error, so a bare try/except
    around one shared session turns the first failure into
    `InFailedSqlTransaction` for every statement after it — the rest silently
    no-op and log a misleading reason (R4-T0-01). One nested transaction per
    statement keeps each outcome independent, so a genuinely broken migration is
    the only thing that reports as broken.
    """
    failed = []
    for sql in statements:
        try:
            with db.begin_nested():
                db.execute(text(sql))
        except Exception as e:
            failed.append(sql)
            # str(sql): the formatter must not be the thing that raises. A
            # non-string statement (a TextClause, or anything a caller passes by
            # mistake) already failed above; calling .split() on it here would
            # throw out of the except block and abandon every statement left in
            # the list — the exact silent no-op this per-statement loop exists to
            # prevent (R4-E2E-03).
            logger.warning(
                "Migration skipped: %s -- statement: %s",
                str(e).strip()[:300], " ".join(str(sql).split())[:120],
            )
    db.commit()
    return failed


# Named, because run_migrations() must be able to tell whether this one statement
# failed before it lets the backfill query the column.
_ADD_COUNTRY_COLUMN = "ALTER TABLE searches ADD COLUMN IF NOT EXISTS country VARCHAR"


# QA F9 / T6-01: composite indexes for the per-account filter (the scoped queries always
# carry `account_id = ...`). Names match the Index(...) entries on the models, so a fresh
# create_all() builds the same set. Idempotent.
ACCOUNT_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_jobs_acct_status ON jobs (account_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_acct_discovered ON jobs (account_id, discovered_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_acct_score ON jobs (account_id, best_cv_score DESC NULLS LAST)",
    "CREATE INDEX IF NOT EXISTS ix_applications_acct_status_updated ON applications (account_id, status, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_llm_call_log_acct_created ON llm_call_log (account_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_job_runs_acct_started ON job_runs (account_id, started_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_scrape_log_acct_company ON scrape_log (account_id, company_id)",
]


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
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cv_score_names JSON",   # 3.1: score keys are résumé ids
        # 3.1: the posting a job is, whatever link spelled it (scraper/_shared/posting_links.py)
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS apply_url VARCHAR",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS posting_key VARCHAR",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS duplicate_of UUID REFERENCES jobs(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_jobs_acct_posting_key ON jobs (account_id, posting_key)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_duplicate_of ON jobs (duplicate_of)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS copy_kind VARCHAR(10)",
        # 3.2: is the posting still open (still_open.py)
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS open_state VARCHAR(10)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS open_reason VARCHAR",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS open_checked_at TIMESTAMPTZ",
        # 3.2: whether the job's link reaches the employer's site (link_kinds.py)
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS link_kind VARCHAR(12)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_acct_link_kind ON jobs (account_id, link_kind)",
        # 3.2: a role skipped in one place, shown again in another
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS same_role_as UUID REFERENCES jobs(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_jobs_acct_content_hash ON jobs (account_id, content_hash)",
        # 3.2: title variants ("Sr" / "Senior") of one role (same_role.role_hash)
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS role_hash VARCHAR",
        "CREATE INDEX IF NOT EXISTS ix_jobs_acct_role_hash ON jobs (account_id, role_hash)",
        # 3.2: postings missing from full company scrapes (missing_postings.py)
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS missed_scrapes INTEGER",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS board_signature VARCHAR(64)",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS board_count INTEGER",
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
        "CREATE TABLE IF NOT EXISTS resumes (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR NOT NULL, is_base BOOLEAN DEFAULT TRUE, parent_id UUID REFERENCES resumes(id) ON DELETE SET NULL, job_id UUID REFERENCES jobs(id) ON DELETE SET NULL, template VARCHAR DEFAULT 'garamond_alt', page_format VARCHAR DEFAULT 'letter', json_data JSONB DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE TABLE IF NOT EXISTS tracer_links (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token VARCHAR(10) UNIQUE NOT NULL, resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE, destination_url VARCHAR NOT NULL, source_label VARCHAR NOT NULL, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW())",
        "CREATE INDEX IF NOT EXISTS idx_tracer_links_token ON tracer_links(token)",
        "CREATE TABLE IF NOT EXISTS tracer_click_events (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tracer_link_id UUID NOT NULL REFERENCES tracer_links(id) ON DELETE CASCADE, clicked_at TIMESTAMPTZ DEFAULT NOW() NOT NULL, device_type VARCHAR DEFAULT 'unknown', ua_family VARCHAR DEFAULT 'unknown', os_family VARCHAR DEFAULT 'unknown', referrer_host VARCHAR, ip_hash VARCHAR, is_likely_bot BOOLEAN DEFAULT FALSE)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS loc_country VARCHAR(2)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS loc_region VARCHAR(64)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS loc_city VARCHAR(120)",
        # region was VARCHAR(3) at first (US/CA codes); regions elsewhere are names ("Hesse");
        # city is bounded because it is indexed (a btree entry caps near 2704 bytes)
        "ALTER TABLE jobs ALTER COLUMN loc_region TYPE VARCHAR(64)",
        "ALTER TABLE jobs ALTER COLUMN loc_city TYPE VARCHAR(120)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_loc_country ON jobs(loc_country)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_loc_region ON jobs(loc_region)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_loc_city ON jobs(loc_city)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS arr_remote BOOLEAN",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS arr_hybrid BOOLEAN",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS arr_onsite BOOLEAN",
        "CREATE INDEX IF NOT EXISTS ix_jobs_arr_remote ON jobs(arr_remote)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_arr_hybrid ON jobs(arr_hybrid)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_arr_onsite ON jobs(arr_onsite)",
        """CREATE TABLE IF NOT EXISTS job_locations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            country VARCHAR(2),
            region VARCHAR(64),
            city VARCHAR(120),
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT uq_job_location UNIQUE (job_id, country, region, city)
        )""",
        "ALTER TABLE job_locations ALTER COLUMN region TYPE VARCHAR(64)",
        "ALTER TABLE job_locations ALTER COLUMN city TYPE VARCHAR(120)",
        "CREATE INDEX IF NOT EXISTS ix_job_locations_job_id ON job_locations(job_id)",
        "CREATE INDEX IF NOT EXISTS ix_job_locations_country ON job_locations(country)",
        "CREATE INDEX IF NOT EXISTS ix_job_locations_region ON job_locations(region)",
        "CREATE INDEX IF NOT EXISTS ix_job_locations_city ON job_locations(city)",
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
        # Fix FK drift: the CREATE TABLE above is a no-op on live DBs where
        # create_all() already built the table with no ondelete; re-align to SET NULL.
        """ALTER TABLE llm_call_log DROP CONSTRAINT IF EXISTS llm_call_log_job_id_fkey""",
        """ALTER TABLE llm_call_log ADD CONSTRAINT llm_call_log_job_id_fkey FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL""",
        "ALTER TABLE llm_call_log ADD COLUMN IF NOT EXISTS provider VARCHAR NOT NULL DEFAULT ''",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS best_cv_score FLOAT",
        "CREATE INDEX IF NOT EXISTS ix_jobs_best_cv_score ON jobs(best_cv_score)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cache_error TEXT",
        # cv_scores is declared Column(JSON), so create_all() builds it as native
        # `json` on a fresh DB and as `jsonb` on DBs predating that change. The
        # jsonb_* functions have no `json` overload, so every reference is cast
        # explicitly — the statement then works on both shapes.
        """UPDATE jobs SET best_cv_score = (
            SELECT MAX(CAST(value AS FLOAT))
            FROM jsonb_each_text(cv_scores::jsonb)
            WHERE value ~ '^[0-9]+(\\.[0-9]+)?$'
        ) WHERE cv_scores IS NOT NULL
          AND jsonb_typeof(cv_scores::jsonb) = 'object'
          AND cv_scores::jsonb != '{}'::jsonb
          AND best_cv_score IS NULL""",
        # Retire screening/phone_screen/final_round statuses onto
        # applied/interview/offer/rejected; status_transitions is left as-is.
        "UPDATE applications SET status = 'applied' WHERE status = 'screening'",
        "UPDATE applications SET status = 'interview' WHERE status IN ('phone_screen', 'final_round')",
        "ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS target_job_id UUID",
        # Add the missing FK constraint for existing DBs where ADD COLUMN didn't emit REFERENCES.
        # Idempotent via DROP ... IF EXISTS. Mirrors the llm_call_log pattern above.
        "ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS job_runs_target_job_id_fkey",
        "ALTER TABLE job_runs ADD CONSTRAINT job_runs_target_job_id_fkey FOREIGN KEY (target_job_id) REFERENCES jobs(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_job_runs_target_job_id ON job_runs(target_job_id)",
        """ALTER TABLE companies ADD COLUMN IF NOT EXISTS selected_resume_ids JSONB DEFAULT '[]'::jsonb""",
        # ADD COLUMN is a no-op where create_all() already built the column from
        # Column(JSON), so it can be native `json` here too. Cast every reference.
        # Translate selected_cv_ids → selected_resume_ids by matching CV.version to Resume.name.
        # Idempotent: only runs while selected_cv_ids still exists and selected_resume_ids is empty.
        """DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'companies' AND column_name = 'selected_cv_ids')
  THEN
    UPDATE companies c
       SET selected_resume_ids = COALESCE(translated.ids, '[]'::jsonb)
      FROM (
        SELECT co.id AS cid,
               jsonb_agg(r.id::text) AS ids
          FROM companies co
          CROSS JOIN LATERAL jsonb_array_elements_text(co.selected_cv_ids::jsonb) AS cid_str(val)
          JOIN cvs cv ON cv.id::text = cid_str.val
          JOIN resumes r ON r.name = cv.version AND r.is_base = TRUE
         GROUP BY co.id
      ) AS translated
     WHERE c.id = translated.cid
       AND (c.selected_resume_ids IS NULL OR c.selected_resume_ids::jsonb = '[]'::jsonb);
  END IF;
END $$;""",
        """ALTER TABLE companies DROP COLUMN IF EXISTS selected_cv_ids""",
        """CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY,
    contact JSONB DEFAULT '{}'::jsonb,
    work_auth JSONB DEFAULT '{}'::jsonb,
    demographics JSONB DEFAULT '{}'::jsonb,
    compensation JSONB DEFAULT '{}'::jsonb,
    preferences JSONB DEFAULT '{}'::jsonb,
    resume_content JSONB DEFAULT '{}'::jsonb,
    qa_bank JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)""",
        # writing_samples retired — voice now comes from the paired resume + persona
        # preferences (see cover-letter feature). Idempotent drop for existing DBs.
        "ALTER TABLE personas DROP COLUMN IF EXISTS writing_samples",
        # Tracer links can now belong to a cover letter too — add the FK + relax
        # resume_id to nullable. Idempotent for existing DBs.
        "ALTER TABLE tracer_links ADD COLUMN IF NOT EXISTS cover_letter_id UUID REFERENCES cover_letters(id) ON DELETE CASCADE",
        "ALTER TABLE tracer_links ALTER COLUMN resume_id DROP NOT NULL",
        # Drop the legacy cvs table — Resume + Persona is the new world.
        "DROP TABLE IF EXISTS cvs",
        # Per-source outcome for multi-board search runs, so a source that hard-fails
        # (ZipRecruiter 403) stops looking like one that simply found nothing.
        "ALTER TABLE scrape_log ADD COLUMN IF NOT EXISTS source_breakdown JSONB",
        # Per-entity acknowledgement of a scrape warning: /health/entities stops
        # counting it while its newest ScrapeLog row is no newer than this stamp.
        "ALTER TABLE searches ADD COLUMN IF NOT EXISTS warning_acknowledged_at TIMESTAMPTZ",
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS warning_acknowledged_at TIMESTAMPTZ",
        # searches.country picks the Indeed domain and API country header. The
        # column arrives WITHOUT a default on purpose: `ADD COLUMN ... DEFAULT x`
        # writes x into every existing row, and the NULL rows are exactly the
        # ones _backfill_search_country() below must still read. `SET DEFAULT`
        # applies to later inserts only, so the two statements are safe in this order.
        _ADD_COUNTRY_COLUMN,
        "ALTER TABLE searches ALTER COLUMN country SET DEFAULT 'usa'",
    ] + ACCOUNT_INDEX_STATEMENTS
    # The account_id columns go first: every ORM query below selects them, so on an
    # existing database they must exist before any model is loaded.
    run_migration_statements(db, _account_column_statements())
    _migrate_settings_scoping(db)
    failed = run_migration_statements(db, migrations)

    # The backfill reads searches.country. Without the column the SELECT raises
    # out of run_seeds() and out of the FastAPI lifespan, and the container
    # restarts forever — the exact whole-list abort run_migration_statements()
    # exists to prevent. Skip the backfill instead, and say so.
    if _ADD_COUNTRY_COLUMN in failed:
        logger.warning("searches.country was not added — skipping the country backfill")
    else:
        try:
            # Order matters: the backfill reads the country out of the location
            # text, so it must run before the strip removes that text.
            _backfill_search_country(db)
            _strip_country_from_search_location(db)
        except Exception as e:
            db.rollback()
            logger.warning("Country migration skipped: %s", str(e).strip()[:300])

    _rewrite_retired_status_transitions(db)
    _migrate_accounts(db)
    _migrate_unique_per_account(db)


# MT-4: install-wide UNIQUE constraints become per-account, so two accounts can each hold
# a company called "Acme" and the same posting. New index first (if it cannot be built the
# old constraint stays), then the old single-column constraint goes. Idempotent; the names
# match the UniqueConstraints on the models, so a fresh create_all() makes these no-ops.
UNIQUE_PER_ACCOUNT_STATEMENTS = [
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_account_name ON companies (account_id, name)",
    "ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_name_key",
    "DROP INDEX IF EXISTS companies_name_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_account_external_id ON jobs (account_id, external_id)",
    "ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_external_id_key",
    "DROP INDEX IF EXISTS jobs_external_id_key",
    # MT-5: one Persona per account. Every row before MT-5 was id 1 inserted with an
    # explicit id, so the serial sequence never moved; point it past the highest id so
    # the first member's Persona does not collide with the owner's row.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_personas_account ON personas (account_id)",
    "SELECT setval(pg_get_serial_sequence('personas', 'id'), "
    "COALESCE((SELECT MAX(id) FROM personas), 0) + 1, false)",
]


def _migrate_unique_per_account(db):
    """Postgres only: SQLite test databases are built from the models, which already
    declare the composite constraints."""
    if db.get_bind().dialect.name != "postgresql":
        return
    run_migration_statements(db, UNIQUE_PER_ACCOUNT_STATEMENTS)


# Multi-tenancy (MT-1): every user-data table carries a nullable account_id. The
# plan calls the activity table "activity_log"; the real name is activity_log_v2.
# job_locations follows jobs and tracer_click_events follows tracer_links.
ACCOUNT_TABLES = [
    "searches", "companies", "jobs", "applications", "interviews", "resumes",
    "cover_letters", "personas", "tracer_links", "activity_log_v2", "llm_call_log",
    "job_runs", "scrape_log",
]


def _account_column_statements() -> list:
    stmts = []
    for t in ACCOUNT_TABLES:
        stmts.append(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES accounts(id) ON DELETE CASCADE")
        stmts.append(f"CREATE INDEX IF NOT EXISTS ix_{t}_account_id ON {t}(account_id)")
    # MT-8: rows of one shared fetch (one per subscribing account) share a run_id. Here,
    # with the account columns, because ORM reads of scrape_log select it.
    stmts.append("ALTER TABLE scrape_log ADD COLUMN IF NOT EXISTS run_id UUID")
    stmts.append("CREATE INDEX IF NOT EXISTS ix_scrape_log_run_id ON scrape_log(run_id)")
    return stmts


# MT-9: settings rows gain account_id (NULL = install value, every existing row) and a
# surrogate id primary key; uniqueness moves from PRIMARY KEY(key) to one install row per
# key + one row per (account, key). The unique indexes are built before the old key
# primary key is dropped, so key uniqueness never lapses. Idempotent; a fresh
# create_all() already has this shape (index names match the Setting model).
SETTINGS_SCOPING_STATEMENTS = [
    "ALTER TABLE settings ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES accounts(id) ON DELETE CASCADE",
    "CREATE INDEX IF NOT EXISTS ix_settings_account_id ON settings(account_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_settings_install_key ON settings (key) WHERE account_id IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_settings_account_key ON settings (account_id, key) WHERE account_id IS NOT NULL",
    "ALTER TABLE settings ADD COLUMN IF NOT EXISTS id SERIAL",
    # R3-06: the old primary key is dropped by its actual name (a restored or renamed
    # table may not call it settings_pkey).
    """DO $$
DECLARE pk_name text;
BEGIN
  SELECT c.conname INTO pk_name FROM pg_constraint c
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
    WHERE c.conrelid = 'settings'::regclass AND c.contype = 'p' AND a.attname = 'key'
    LIMIT 1;
  IF pk_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE settings DROP CONSTRAINT %I', pk_name);
    ALTER TABLE settings ADD CONSTRAINT settings_pkey PRIMARY KEY (id);
  END IF;
END $$""",
]


def _migrate_settings_scoping(db):
    """Postgres only (SQLite test databases are built from the models). Runs before any
    ORM read of settings, which selects the new columns."""
    if db.get_bind().dialect.name != "postgresql":
        return
    run_migration_statements(db, SETTINGS_SCOPING_STATEMENTS)


def _owner_display_name(db) -> str:
    """Persona header name (first + last) when set, else "Owner"."""
    from backend.models.db import Persona
    try:
        persona = db.query(Persona).order_by(Persona.id).first()
        contact = (persona.contact if persona else None) or {}
        name = " ".join(str(contact.get(k) or "").strip() for k in ("first_name", "last_name")).strip()
        return name or str(contact.get("name") or "").strip() or "Owner"
    except Exception:
        db.rollback()
        return "Owner"


def _migrate_accounts(db):
    """Create the owner account if none exists and give every row that has no account to
    it (the columns themselves are added at the top of run_migrations). Idempotent."""
    from sqlalchemy import update
    from backend.models.db import ACCOUNT_COLORS, Account, Base, get_owner_id

    owner_id = get_owner_id(db)
    if owner_id is None:
        owner = Account(name=_owner_display_name(db), color=ACCOUNT_COLORS[0], role="owner")
        db.add(owner)
        db.commit()
        owner_id = owner.id
        logger.info("Created owner account %r", owner.name)

    for t in ACCOUNT_TABLES:
        table = Base.metadata.tables[t]
        try:
            with db.begin_nested():
                db.execute(update(table).where(table.c.account_id.is_(None)).values(account_id=owner_id))
        except Exception as e:
            logger.warning("Account backfill skipped for %s: %s", t, str(e).strip()[:200])
    db.commit()


def _backfill_search_country(db):
    """One-shot: read a country out of each existing search's location text.

    Only rows whose country is still NULL are visited, so this runs once per
    row. Rows written after the migration carry the column default.
    """
    from backend.countries import DEFAULT_COUNTRY, country_from_location, split_country_suffix
    from backend.models.db import Search

    rows = db.query(Search).filter(Search.country.is_(None)).all()
    if not rows:
        return
    for search in rows:
        search.country = country_from_location(search.location)
        # A region code is not a country: "Toronto, ON" reads as no country at
        # all and falls to DEFAULT_COUNTRY. That guess used to be nearly
        # harmless, because LinkedIn still received the region. The scraper now
        # appends the guessed country to it, so an operator must be able to see
        # which rows were guessed and correct them.
        if str(search.location or "").strip() and split_country_suffix(search.location)[1] is None:
            logger.warning(
                "Search %s: location %r names no country — the backfill guessed %s",
                search.name, search.location, DEFAULT_COUNTRY,
            )
    db.commit()
    logger.info("Backfilled searches.country for %d row(s)", len(rows))


def _strip_country_from_search_location(db):
    """Remove the country segment from each keyword search's location text.

    The migration needs this once. It is idempotent afterwards, and it also
    cleans a country a user types into the field later.

    `location` holds a city or a region, and `country` is the single country
    source. The scraper appends the label of `country` to the location, so a
    country left in the text would appear twice.

    Three rules keep the result stable and honest:

    1. `normalize_country()` decides what a country segment is, so "Toronto, ON"
       stays whole and "Toronto, Canada" becomes "Toronto".
    2. The last segment always stays. "Luxembourg, Luxembourg" becomes
       "Luxembourg" and stops there; without this rule every restart would strip
       one more segment and widen the search to the whole country.
    3. A row whose text disagrees with the stored country keeps the country,
       because the user picked that field, and the row is logged.

    Only `keyword` rows are touched. They are the only rows the jobspy
    composition reads. `jobright` reads `search.location` raw and drops the
    parameter when the text is empty, so rewriting its rows would move this same
    defect to a board this change never measured.
    """
    from backend.countries import split_country_suffix
    from backend.models.db import Search

    changed = 0
    rows = db.query(Search).filter(
        Search.location.isnot(None), Search.search_mode == "keyword"
    ).all()
    for search in rows:
        place, found = split_country_suffix(search.location)
        if found is None:
            continue
        if search.country and found != search.country:
            logger.warning(
                "Search %s: location said %s but country is %s — keeping country",
                search.name, found, search.country,
            )
        if not place:
            continue      # only a country name: there is no place to keep
        # Repeat inside this one pass, so a name that repeats itself settles now
        # instead of losing a segment on every later restart.
        while True:
            inner, more = split_country_suffix(place)
            if more is None or not inner:
                break
            place = inner
        search.location = place
        changed += 1
    if changed:
        db.commit()
        logger.info("Removed the country from searches.location for %d row(s)", changed)


_RETIRED_STATUS_REMAP = {
    "screening": "applied",
    "phone_screen": "interview",
    "final_round": "interview",
}


def _rewrite_retired_status_transitions(db):
    """One-shot: remap retired statuses in Application.status_transitions, drop resulting self-transitions and collapse duplicates, so Sankey shows no ghost nodes."""
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
        # Runs unscoped: the name is unique per account only (MT-4), so set every account's row.
        for company in db.query(Company).filter(Company.name == name).all():
            if not company.h1b_slug:
                company.h1b_slug = slug
    db.commit()


def cleanup_removed_settings(db):
    """Remove settings that have been removed from DEFAULT_SETTINGS."""
    removed_keys = [
        # 3.2: two LinkedIn sessions, each with its own Sign in, replaced the switch
        "linkedin_use_mock_account",
        # the employer-link lookup runs after every scrape at a fixed pace (3.2 had a cron)
        "linkedin_lookup_cron", "linkedin_lookup_per_run",
        "followup_reminder_days",
        "h1b_exclusion_phrases",
        "language_exclude_phrases",
        "default_cv_id",
        # Seeded but read by no code: max_jobs_per_scrape promised a per-run cap
        # nothing enforced; company_domains/ats_domains were a retired Gmail-detection design.
        "max_jobs_per_scrape",
        "company_domains",
        "ats_domains",
        # Duplicated the Persona's own decline_demographics checkbox.
        "autofill_decline_self_id",
        # openai_compat provider removed — these were only for it.
        "llm_base_url",
        "llm_fallback_base_url",
        # structured-autofill on/off + trigger live in the extension popup, not
        # server settings — they're per-browser preferences.
        "autofill_structured_enabled",
        "autofill_structured_trigger",
    ]
    for key in removed_keys:
        # the install row and every account's own row
        for row in db.query(Setting).filter(Setting.key == key).all():
            db.delete(row)
    db.commit()


def migrate_cv_terminology(db):
    """Rename 'CV'/'CVs' -> 'Resume'/'Resumes' in editable prompt-text settings; word-boundary matching leaves template tokens like CV_NAMES_HERE intact."""
    import re
    for key in ("scoring_rubric",):
        for row in _all_rows(db, key):   # R3-04: members' own rows too
            if not row.value:
                continue
            new = re.sub(r"\bCVs\b", "Resumes", row.value)
            new = re.sub(r"\bCV\b", "Resume", new)
            if new != row.value:
                row.value = new
    db.commit()


def _all_rows(db, key: str) -> list:
    """The install row and every account's own row of `key` (R3-04: a startup migration
    that rewrites a value applies to members on 'own' as well), install first."""
    rows = db.query(Setting).filter(Setting.key == key).all()
    return sorted(rows, key=lambda r: r.account_id is not None)


def migrate_llm_settings(db):
    """Refresh llm_models_list to current defaults, re-point openai_compat settings to openai, and rename the dated haiku model alias."""
    # Additive seed: default models are offered ONCE (tracked in llm_seeded_models);
    # after that the user's list is authoritative, but genuinely-new defaults still propagate.
    row = install_row(db, "llm_models_list")
    seen_row = install_row(db, "llm_seeded_models")
    if seen_row is None:
        seen_row = Setting(key="llm_seeded_models", value="[]",
                           description="Internal: default model keys already offered, so user deletions persist across restarts")
        db.add(seen_row)
    mkey = lambda m: f'{m.get("provider")}|{m.get("model")}'
    default_list = json.loads(DEFAULT_SETTINGS["llm_models_list"][0])
    try:
        seen_before = set(json.loads(seen_row.value or "[]"))
    except (ValueError, TypeError):
        seen_before = set()
    # Defaults this release offers for the first time; they reach every list below.
    new_defaults = [d for d in default_list if mkey(d) not in seen_before]

    def _merge(list_row):
        try:
            current = json.loads(list_row.value)
        except (ValueError, TypeError):
            current = []
        if not isinstance(current, list):
            current = []
        current = [m for m in current if isinstance(m, dict) and m.get("provider") != "openai_compat"]
        have = {mkey(m) for m in current}
        for d in new_defaults:
            if mkey(d) not in have:   # new default the user never removed
                current.append(d)
                have.add(mkey(d))
        list_row.value = json.dumps(current)

    if row and row.value:
        _merge(row)
        seen_row.value = json.dumps(sorted(seen_before | {mkey(d) for d in default_list}))
    # R3-04: a member on its own Models section keeps its own list; it gets the same new
    # defaults (one seen-list for the install, so a default it deleted stays deleted).
    for member_row in db.query(Setting).filter(Setting.key == "llm_models_list",
                                               Setting.account_id.isnot(None)).all():
        if member_row.value:
            _merge(member_row)

    provider_keys = ["llm_provider", "llm_fallback_provider", "email_llm_provider",
                     "cv_tailor_llm_provider", "cover_letter_llm_provider", "autofill_llm_provider",
                     "scoring_llm_provider"]
    for key in provider_keys:
        for r in _all_rows(db, key):
            if r.value == "openai_compat":
                r.value = "openai"

    model_keys = ["llm_model", "llm_fallback_model", "email_llm_model",
                  "cv_tailor_llm_model", "cover_letter_llm_model", "autofill_llm_model",
                  "scoring_llm_model"]
    for key in model_keys:
        for r in _all_rows(db, key):
            if r.value == "claude-haiku-4-5-20251001":
                r.value = "claude-haiku-4-5"

    db.commit()


# Marker of the one-time L-03 cleanup below (install row, never served, not writable).
LOCAL_URLS_CLEARED_KEY = "llm_local_seed_cleared"


def clear_seeded_local_urls(db) -> list:
    """One time per install (L-03): blank `lmstudio_base_url` / `ollama_base_url` where the value
    still gives the same address as an empty box would (the env var, else the built-in default).

    The first build with these settings seeded them with `LMSTUDIO_BASE_URL` / `OLLAMA_BASE_URL`
    or the default, so the row was never empty and a later `.env` edit was ignored. A value that
    equals today's env/default address is that seed (or the same address typed by hand): blanking
    it sends every call to the same server as before and lets `.env` work again. Any other value
    was set on purpose, or no longer matches the env, so it stays. The marker row keeps the step
    from running again, so an address typed after this release is never touched. Returns the
    keys it blanked."""
    from backend.analyzer.llm_client import local_base_url_fallback
    if install_row(db, LOCAL_URLS_CLEARED_KEY) is not None:
        return []
    cleared = []
    for provider, (key, _env, _default) in LOCAL_LLM_URLS.items():
        row = install_row(db, key)
        value = (row.value or "").strip().rstrip("/") if row is not None else ""
        if value and value == local_base_url_fallback(provider):
            row.value = ""
            cleared.append(key)
    db.add(Setting(key=LOCAL_URLS_CLEARED_KEY, value="1",
                   description="Internal: the seeded LM Studio / Ollama addresses were cleared once (L-03)"))
    db.commit()
    if cleared:
        logger.info(f"Cleared the seeded local model addresses (env/default applies): {', '.join(cleared)}")
    return cleared



# Marker of the one-time per-provider key migration below (install row, never served, not writable).
PROVIDER_KEYS_MIGRATED_KEY = "llm_provider_keys_migrated"
# Slot prefixes in the order a conflict is settled: the Primary's key wins.
_KEY_SLOT_ORDER = (("", "llm"), ("scoring_", "scoring_llm"), ("cv_tailor_", "cv_tailor_llm"),
                   ("cover_letter_", "cover_letter_llm"), ("autofill_", "autofill_llm"),
                   ("email_", "email_llm"), ("fallback", "llm_fallback"))


def migrate_llm_provider_keys(db) -> dict:
    """Once per install (3.1): copy each account's per-slot API keys into the per-provider keys.

    For every scope (the install rows, then each account that has slot-key rows of its own) a
    slot's key counts for the slot's *effective* provider, read from that scope's own rows: the
    Primary's `llm_provider` (default claude_api); a feature slot's own provider, else the
    Primary's; the fallback's own provider only. A key whose slot has no provider (a switched-off
    override, an orphan) is not migrated, so it never starts billing. A provider key already set
    is never overwritten. When one provider had different keys the Primary's wins and the log
    names the slots dropped (never values); the legacy rows stay for a downgrade. The marker
    keeps a key the user clears later from coming back. Returns {scope: {setting: slot}}."""
    from backend.accounts.settings import LEGACY_LLM_KEY_SETTINGS, PROVIDER_KEY_SETTINGS
    if install_row(db, PROVIDER_KEYS_MIGRATED_KEY) is not None:
        return {}
    scopes = [None] + sorted({r.account_id for r in db.query(Setting)
                              .filter(Setting.key.in_(LEGACY_LLM_KEY_SETTINGS),
                                      Setting.account_id.isnot(None)).all()}, key=str)

    def value(acct, key):
        row = (db.query(Setting).filter(Setting.key == key, Setting.account_id == acct).first()
               if acct is not None else install_row(db, key))
        return ((row.value if row is not None else "") or "").strip()

    written = {}
    for acct in scopes:
        primary = value(acct, "llm_provider") or "claude_api"
        candidates: dict = {}
        for _prefix, base in _KEY_SLOT_ORDER:
            key = value(acct, f"{base}_api_key")
            if not key:
                continue
            own = value(acct, f"{base}_provider")
            if base == "llm":
                provider = primary
            elif base == "llm_fallback":
                provider = own
            else:
                provider = own or ""      # no provider of its own: the key was never in use
            if provider in PROVIDER_KEY_SETTINGS:
                candidates.setdefault(provider, []).append((base, key))
        scope = str(acct) if acct is not None else "install"
        for provider, found in candidates.items():
            setting = PROVIDER_KEY_SETTINGS[provider]
            if value(acct, setting):
                continue                  # already set in the new box: never overwritten
            slot, key = found[0]
            dropped = sorted({b for b, k in found[1:] if k != key})
            if dropped:
                logger.warning(f"API key migration ({scope}): {provider} had different keys; kept "
                               f"the {slot} slot's, not {', '.join(dropped)} (old rows kept)")
            put_setting(db, setting, key, account_id=acct)
            written.setdefault(scope, {})[setting] = slot
    db.add(Setting(key=PROVIDER_KEYS_MIGRATED_KEY, value="1",
                   description="Internal: per-slot API keys were copied to per-provider keys once (3.1)"))
    db.commit()
    if written:
        logger.info(f"Moved API keys to one per provider: {written}")
    return written


def _chunk_then_commit(db, model, ids):
    """The rows with these ids, then a commit once the caller has changed them."""
    yield from db.query(model).filter(model.id.in_(ids)).all()
    db.commit()


# Marker of the one-time score-key migration below (install row, never served, not writable).
SCORE_KEYS_MIGRATED_KEY = "cv_score_keys_migrated"


def migrate_cv_score_keys(db, batch: int = 500) -> dict:
    """Once per install (3.1): re-key job scores from résumé names to résumé ids.

    Per account, a name maps to that account's base résumé of that name (the scorer keyed by
    base names; a tailored copy scored under "Tailored"); when two bases share a name, the
    newest wins and the log names the others, never their content.
    In every job of the account, the keys of `cv_scores` and `scoring_report` and the value of
    `best_cv` that are such a name become the id, and `cv_score_names` records {id: name}. A
    key no résumé has (a deleted or renamed one, "Tailored", "Persona", "_skipped") stays as it
    is and is still shown under its own text. The marker keeps it from running twice.
    Returns {account id: jobs changed}."""
    from sqlalchemy.orm.attributes import flag_modified
    from backend.analyzer.score_keys import PERSONA, TAILORED, is_resume_key
    from backend.models.db import Account, Job, Resume
    if install_row(db, SCORE_KEYS_MIGRATED_KEY) is not None:
        return {}
    changed: dict = {}
    for (account_id,) in db.query(Account.id).all():
        name_to_id: dict = {}
        dropped: dict = {}
        rows = (db.query(Resume.id, Resume.name, Resume.created_at)
                .filter(Resume.account_id == account_id, Resume.is_base == True).all())  # noqa: E712
        # oldest first, so the newest of two same-named bases ends up in the map
        for rid, name, created in sorted(rows, key=lambda r: r[2].timestamp() if r[2] else 0):
            if not name or name in (TAILORED, PERSONA):
                continue
            if name in name_to_id:
                dropped.setdefault(name, []).append(name_to_id[name])
            name_to_id[name] = str(rid)
        for name, older in dropped.items():
            logger.warning(f"Score keys ({account_id}): {len(older) + 1} résumés are named "
                           f"{name!r}; their scores go to the newest ({name_to_id[name]})")
        if not name_to_id:
            continue
        n = 0
        ids = [jid for (jid,) in db.query(Job.id).filter(Job.account_id == account_id,
                                                         Job.cv_scores.isnot(None)).all()]
        # chunks committed one by one (idempotent: a key that is already an id is never a name)
        jobs = (job for i in range(0, len(ids), batch)
                for job in _chunk_then_commit(db, Job, ids[i:i + batch]))
        for job in jobs:
            scores = job.cv_scores if isinstance(job.cv_scores, dict) else None
            if not scores:
                continue
            mapping = {k: name_to_id[k] for k in scores if k in name_to_id and not is_resume_key(k)}
            report = job.scoring_report if isinstance(job.scoring_report, dict) else None
            nested = report is not None and "summary" not in report
            if nested:
                mapping.update({k: name_to_id[k] for k in report if k in name_to_id})
            best = job.best_cv if job.best_cv in name_to_id else None
            if not mapping and not best:
                continue
            job.cv_scores = {mapping.get(k, k): v for k, v in scores.items()}
            flag_modified(job, "cv_scores")
            if nested:
                job.scoring_report = {mapping.get(k, k): v for k, v in report.items()}
                flag_modified(job, "scoring_report")
            if best:
                job.best_cv = name_to_id[best]
            names = dict(job.cv_score_names or {})
            names.update({rid: name for name, rid in mapping.items()})
            if best:
                names[name_to_id[best]] = best
            job.cv_score_names = names
            n += 1
        db.commit()
        if n:
            changed[str(account_id)] = n
    db.add(Setting(key=SCORE_KEYS_MIGRATED_KEY, value="1",
                   description="Internal: job scores were re-keyed from résumé names to ids once (3.1)"))
    db.commit()
    if changed:
        logger.info(f"Job scores now keyed by résumé id: {changed}")
    return changed


# Marker of the posting-key backfill below: the reader version the stored keys were read with
# (install row, never served, not writable). 3.1 wrote "1".
POSTING_KEYS_MIGRATED_KEY = "posting_keys_migrated"


def migrate_posting_keys(db, batch: int = 1000) -> dict:
    """On start, when the stored posting keys were read by older readers (postings.READER_VERSION):
    key every stored job again and bring its duplicates in line (scraper/_shared/posting_links.py).

    Every job gets `role_hash` (same_role.role_hash), `posting_key` from its links, and `apply_url` when its link wraps the employer's
    posting (a click tracker); no request is made. A key a row took over from its duplicate (an
    employer key on a board listing) is kept when its own link names no employer posting. Then each
    account is relinked (posting_links.relink_account): duplicates linked by company and title alone,
    without a shared key or the same text, go back to the feed, and untouched rows that share a key or
    are one role become duplicates. Rows the user acted on are never changed.
    Returns {"rekeyed": n, "unlinked": n, "linked": n}."""
    from backend.models.db import Account, Job
    from backend.scraper._shared.link_kinds import classify
    from backend.scraper._shared.posting_links import employer_link, key_of, relink_account
    from backend.scraper._shared.postings import READER_VERSION, is_employer_key
    from backend.scraper._shared.same_role import role_hash
    row = install_row(db, POSTING_KEYS_MIGRATED_KEY)
    done = int(row.value) if row is not None and str(row.value or "").isdigit() else 0
    if done >= READER_VERSION:
        return {}
    rekeyed = 0
    ids = [jid for (jid,) in db.query(Job.id).all()]
    jobs = (job for i in range(0, len(ids), batch)
            for job in _chunk_then_commit(db, Job, ids[i:i + batch]))
    for job in jobs:
        job.role_hash = role_hash(job.company, job.title) if (job.company or job.title) else None
        key = key_of(job)
        taken_over = is_employer_key(job.posting_key) and not is_employer_key(key)
        if key != job.posting_key and not taken_over:
            job.posting_key = key
            rekeyed += 1
        if not job.apply_url:
            link = employer_link(job.url)
            if link and link != job.url:
                job.apply_url = link
        classify(job)
    db.commit()
    unlinked = linked = 0
    for (account_id,) in db.query(Account.id).all():
        out = relink_account(db, account_id)
        unlinked += out["unlinked"]
        linked += out["linked"]
    if row is None:
        db.add(Setting(key=POSTING_KEYS_MIGRATED_KEY, value=str(READER_VERSION),
                       description="Internal: the posting-key reader version stored jobs were keyed and linked with"))
    else:
        row.value = str(READER_VERSION)
    db.commit()
    logger.info(f"Posting keys (readers v{READER_VERSION}): {rekeyed} jobs keyed again, "
                f"{unlinked} hidden copies back in the feed (no proof, or a role skipped elsewhere), {linked} untouched copies linked")
    return {"rekeyed": rekeyed, "unlinked": unlinked, "linked": linked}


SEED_SEARCHES = [
    {
        "name": "Extension LI",
        "active": True,
        "search_mode": "linkedin_extension",
        "sources": [],
        "title_include_keywords": [],
        "title_exclude_keywords": [],
        "company_exclude": [],
        "auto_scoring_depth": "off",
    },
    {
        "name": "Extension",
        "active": True,
        "search_mode": "extension",
        "sources": [],
        "title_include_keywords": [],
        "title_exclude_keywords": [],
        "company_exclude": [],
        "auto_scoring_depth": "light",
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

from backend.scraper.search_modes import EXTENSION_MODES as EXTENSION_SEARCH_MODES  # noqa: E402


def ensure_extension_searches(db, account_id) -> int:
    """Give `account_id` its two built-in extension searches ("Extension", "Extension LI")
    when it lacks them. Explicit account filter and stamp, so it works scoped, unscoped
    (startup) and for an account that is not the current one (account creation, MT-11).
    No commit. Returns how many were added."""
    have = {m for (m,) in db.query(Search.search_mode)
            .filter(Search.account_id == account_id,
                    Search.search_mode.in_(EXTENSION_SEARCH_MODES))
            .execution_options(jn_unscoped=True).all()}
    added = 0
    for s in SEED_SEARCHES:
        if s["search_mode"] in EXTENSION_SEARCH_MODES and s["search_mode"] not in have:
            db.add(Search(account_id=account_id, **s))
            added += 1
    return added


def seed_searches(db):
    """Seed the owner's default searches if none of a mode exist, and make sure every
    account has the two built-in extension searches (the save-to-feed and LinkedIn
    capture flows look them up in the caller's account)."""
    from backend.models.db import Account, get_owner_id
    owner_id = get_owner_id(db)
    q = db.query(Search)
    if owner_id is not None:
        q = q.filter(Search.account_id == owner_id)
    existing_modes = {s.search_mode for s in q.all()}
    for s in SEED_SEARCHES:
        if s["search_mode"] not in existing_modes:
            db.add(Search(account_id=owner_id, **s) if owner_id is not None else Search(**s))
    for (acc_id,) in db.query(Account.id).filter(Account.role != "owner").all():
        ensure_extension_searches(db, acc_id)
    # Idempotent rename: self-heal any linkedin_extension search still named
    # "LinkedIn Extension" so fresh DB clones end up labeled "Extension LI".
    legacy = db.query(Search).filter(
        Search.search_mode == "linkedin_extension",
        Search.name == "LinkedIn Extension",
    ).first()
    if legacy:
        legacy.name = "Extension LI"
    db.commit()


def seed_mock_resume(db):
    """Seed a mock base Resume for demonstration and set it as default for all companies; bails if any base Resume already exists."""
    if db.query(Resume).filter(Resume.is_base == True).count() > 0:
        return  # User already has a base resume

    resume = db.query(Resume).filter(Resume.name == "Sample PM", Resume.is_base == True).first()
    if resume is None:
        resume = Resume(
            name="Sample PM",
            is_base=True,
            template="garamond_alt",
            page_format="letter",
            json_data=MOCK_RESUME_JSON,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

    default_row = install_row(db, "default_resume_id")
    if default_row:
        default_row.value = str(resume.id)
    db.commit()

    for company in db.query(Company).all():
        company.selected_resume_ids = [str(resume.id)]
    db.commit()

    logger.info("Seeded mock resume 'Sample PM'")


def seed_persona(db):
    """Ensure the owner's Persona exists with empty nodes (other accounts get theirs on
    first access, backend.accounts.owned.get_persona). Explicit account filter: this runs
    inside unscoped() at startup."""
    from backend.models.db import Persona, get_owner_id
    owner_id = get_owner_id(db)
    q = db.query(Persona)
    if owner_id is not None:
        q = q.filter(Persona.account_id == owner_id)
    if q.first():
        return
    p = Persona(
        account_id=owner_id,
        contact={},
        work_auth={},
        demographics={},
        compensation={},
        preferences={},
        resume_content={},
        qa_bank=[],
    )
    db.add(p)
    db.commit()
    logger.info("Owner Persona seeded with empty nodes")


def migrate_h1b_to_visa_cache(db):
    """One-time: copy legacy companies.h1b_* into visa_cache then drop those columns (Postgres only for the DROP; no-op once the columns are gone)."""
    from backend.models.db import VisaCache
    from sqlalchemy import text

    bind = db.get_bind()
    dialect = bind.dialect.name
    try:
        if dialect == "postgresql":
            cols = {r[0] for r in db.execute(text(
                "select column_name from information_schema.columns where table_name='companies'"))}
        elif dialect == "sqlite":
            cols = {r[1] for r in db.execute(text("PRAGMA table_info(companies)"))}
        else:
            return
    except Exception:
        return
    if "h1b_lca_count" not in cols:
        return  # already migrated, or fresh install

    # 1) Seed visa_cache from the legacy columns (rows with data or a slug).
    try:
        rows = db.execute(text(
            "select name, h1b_slug, h1b_lca_count, h1b_approval_rate, h1b_median_salary, "
            "h1b_last_checked from companies")).fetchall()
    except Exception:
        rows = []
    existing = {r.name_key for r in db.query(VisaCache).all()}
    seeded = 0
    for name, slug, lca, appr, med, checked in rows:
        key = (name or "").strip().lower()
        if not key or key in existing:
            continue
        has = bool((lca or 0) > 0 or (med or 0) > 0)
        if not (has or slug):
            continue
        db.add(VisaCache(name_key=key, country="US", display_name=name, slug=slug,
                         lca_count=lca, approval_rate=appr, median_salary=med,
                         has_data=has, fetched_at=checked))
        existing.add(key)
        seeded += 1
    db.commit()
    logger.info("migrate_h1b_to_visa_cache: seeded %d companies into visa_cache", seeded)

    # 2) Drop the legacy columns (Postgres supports IF EXISTS; SQLite skipped).
    if dialect == "postgresql":
        for col in ("h1b_lca_count", "h1b_approval_rate", "h1b_median_salary", "h1b_last_checked"):
            try:
                db.execute(text(f"ALTER TABLE companies DROP COLUMN IF EXISTS {col}"))
            except Exception as e:
                logger.warning("drop legacy column %s failed: %s", col, e)
        db.commit()


def migrate_autofill_dicts(db):
    """Merge newly-added canonical keys into autofill_field_patterns/autofill_option_synonyms without clobbering the user's edits (only missing top-level keys are added)."""
    for setting_key in ("autofill_field_patterns", "autofill_option_synonyms"):
        default_json = DEFAULT_SETTINGS.get(setting_key, ("{}", ""))[0]
        try:
            defaults = json.loads(default_json)
        except (ValueError, TypeError):
            continue
        # R3-04: the install row and every member's own row
        for row in _all_rows(db, setting_key):
            try:
                stored = json.loads(row.value or "{}")
            except (ValueError, TypeError):
                continue
            if not isinstance(stored, dict):
                continue
            changed = False
            for k, v in defaults.items():
                if k not in stored:
                    stored[k] = v
                    changed = True
            if changed:
                row.value = json.dumps(stored)
    db.commit()


def migrate_dedup_tracking_params(db):
    """Take "jk" out of an already-stored `dedup_tracking_params`, since settings are seeded once and DEFAULT_SETTINGS alone won't fix an existing install."""
    row = install_row(db, "dedup_tracking_params")
    if not row or not row.value:
        return
    try:
        stored = json.loads(row.value)
    except (ValueError, TypeError):
        return
    if not isinstance(stored, list):
        return
    kept = [p for p in stored if str(p).strip().lower() != "jk"]
    if len(kept) == len(stored):
        return
    row.value = json.dumps(kept)
    db.commit()
    try:
        from backend.scraper._shared.dedup import reload_tracking_params
        reload_tracking_params()
    except Exception:
        pass   # the cache loads lazily anyway; a failed eager reload is not fatal


def run_seeds():
    # System code: migrations and seeds see every account (MT-2); new rows go to the owner.
    from backend.accounts.context import unscoped
    db = SessionLocal()
    try:
        with unscoped():
            run_migrations(db)
            seed_settings(db)
            migrate_dedup_tracking_params(db)
            migrate_autofill_dicts(db)
            seed_companies(db)
            seed_h1b_slugs(db)
            seed_searches(db)
            seed_mock_resume(db)
            seed_persona(db)
            cleanup_removed_settings(db)
            migrate_llm_settings(db)
            clear_seeded_local_urls(db)
            migrate_llm_provider_keys(db)
            migrate_cv_score_keys(db)
            migrate_posting_keys(db)
            migrate_cv_terminology(db)
            migrate_h1b_to_visa_cache(db)
    finally:
        db.close()
