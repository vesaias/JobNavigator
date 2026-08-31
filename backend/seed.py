"""Seed settings and companies tables with defaults on first run."""
import logging
import json
import secrets
from backend.models.db import SessionLocal, Setting, Company, Search, Resume
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
    "reject_cron": ("0 4 * * *", "Auto-reject cron (min hour day month dow). Empty = disabled"),
    "backup_cron": ("0 3 * * *", "Backup cron schedule (min hour day month dow). Empty = disabled"),
    "scoring_rubric": ("Score each resume using these criteria (each 0-20, sum to 0-100):\n1. SKILLS MATCH (weight: 20): How many required technical skills/tools does the candidate have?\n2. EXPERIENCE LEVEL (weight: 20): Does seniority/years match? (entry-level resume for senior role = low)\n3. DOMAIN FIT (weight: 20): Has the candidate worked in the same industry/domain?\n4. ROLE ALIGNMENT (weight: 20): Does the candidate's career trajectory match this role type?\n5. REQUIREMENTS MET (weight: 20): Does the candidate meet stated requirements (education, certs, clearance)?\n\nUse the FULL 0-100 range. 90+ = perfect match. 50-70 = decent with gaps. Below 30 = poor match.\nAvoid clustering scores — differentiate meaningfully between resumes and jobs.", "Editable resume scoring rubric"),
    "scoring_output_light": ('Return ONLY this JSON:\n{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "best_cv": "CV_NAME"\n}', "Light scoring output schema"),
    "scoring_output_full": ('Return ONLY this JSON:\n{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "best_cv": "CV_NAME",\n  "breakdown": {"skills": 0-20, "experience": 0-20, "domain": 0-20, "role": 0-20, "requirements": 0-20},\n  "summary": "2-3 sentence assessment of candidate-job fit",\n  "requirement_mapping": [\n    {"requirement": "JD requirement text", "cv_match": "matching CV line or null", "matched": true/false, "severity": "required or preferred"}\n  ],\n  "keyword_coverage_pct": 0-100,\n  "matched_keywords": ["keyword1", "keyword2"],\n  "missing_keywords": ["keyword3", "keyword4"],\n  "hard_blockers": ["blocker if any"],\n  "ats_tip": "one actionable ATS optimization suggestion"\n}', "Full scoring output schema with keyword analysis"),
    "llm_provider": ("claude_api", "LLM provider: claude_api, claude_code, openai, ollama"),
    "llm_model": ("claude-sonnet-5", "LLM model name"),
    "llm_api_key": ("", "API key for OpenAI (not needed for Claude API/Ollama)"),
    "llm_fallback_provider": ("", "Fallback LLM provider (empty = no fallback)"),
    "llm_fallback_model": ("", "Fallback model name"),
    "llm_fallback_api_key": ("", "API key for fallback provider (OpenAI)"),
    "scoring_llm_provider": ("", "Resume scoring provider override (empty = use Primary)"),
    "scoring_llm_model": ("", "Resume scoring model override (empty = use Primary)"),
    "scoring_llm_api_key": ("", "API key for the scoring provider override"),
    "llm_models_list": (json.dumps([
        {"provider": "claude_api", "model": "claude-sonnet-5"},
        {"provider": "claude_api", "model": "claude-sonnet-4-6"},
        {"provider": "claude_api", "model": "claude-opus-5"},
        {"provider": "claude_api", "model": "claude-opus-4-8"},
        {"provider": "claude_api", "model": "claude-opus-4-7"},
        {"provider": "claude_api", "model": "claude-opus-4-6"},
        {"provider": "claude_api", "model": "claude-haiku-4-5"},
        {"provider": "claude_api", "model": "claude-fable-5"},
        {"provider": "claude_code", "model": "claude-sonnet-5"},
        {"provider": "claude_code", "model": "claude-sonnet-4-6"},
        {"provider": "claude_code", "model": "claude-opus-5"},
        {"provider": "claude_code", "model": "claude-opus-4-8"},
        {"provider": "claude_code", "model": "claude-opus-4-7"},
        {"provider": "claude_code", "model": "claude-opus-4-6"},
        {"provider": "claude_code", "model": "claude-haiku-4-5"},
        {"provider": "claude_code", "model": "claude-fable-5"},
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
        # OpenRouter — one key reaches every vendor; slugs are vendor-prefixed.
        # A popular starter set; the full ~420 are fetchable in Settings via the API.
        {"provider": "openrouter", "model": "anthropic/claude-opus-5"},
        {"provider": "openrouter", "model": "anthropic/claude-sonnet-5"},
        {"provider": "openrouter", "model": "openai/gpt-5.6-luna"},
        {"provider": "openrouter", "model": "openai/o3-pro"},
        {"provider": "openrouter", "model": "openai/o4-mini-high"},
        {"provider": "openrouter", "model": "google/gemini-3.7-flash"},
        {"provider": "openrouter", "model": "deepseek/deepseek-v4-pro"},
        {"provider": "openrouter", "model": "deepseek/deepseek-v3.2"},
        {"provider": "openrouter", "model": "meta-llama/llama-4-maverick"},
        {"provider": "openrouter", "model": "x-ai/grok-4.6"},
        {"provider": "openrouter", "model": "mistralai/mistral-large-2512"},
    ]), "Known LLM models per provider (JSON array, user can add custom entries)"),
    "scoring_max_concurrent": ("5", "Max parallel scoring jobs (others queue until a slot opens)"),
    "tailoring_max_concurrent": ("2", "Max concurrent resume-tailoring LLM calls"),
    "tailor_auto_quick_score": ("light", "After tailoring finishes, auto-launch a score chain. Values: 'off' | 'light' | 'full'. Default 'light'. Legacy 'true'='light', 'false'='off'."),
    "prompt_caching_enabled": ("true", "Use Anthropic prompt caching on resume scoring (claude_api only; ~50% cheaper input tokens on same-batch calls). Set false to disable as a rollback lever."),
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
    "cv_tailor_llm_provider": ("", "LLM provider for resume tailoring (empty = use primary llm_provider)"),
    "cv_tailor_llm_model": ("", "LLM model for resume tailoring (empty = use primary llm_model)"),
    "cv_tailor_llm_api_key": ("", "API key for resume tailoring LLM provider"),
    "cv_tailor_prompt": ("Tailor this resume for the job description below.\n\nRules for MAIN bullets[]:\n- Rewrite the summary to target this specific role\n- For each experience bullet: if it benefits from JD keyword alignment, reformulate it. If it's already well-suited, leave it UNCHANGED\n- Keep the same number of bullets per experience entry - do not add or remove\n- Reorder skills to prioritize JD-relevant ones first\n- Do NOT invent new experience, skills, or facts in the main bullets. If something is missing, map to the closest truthful concept\n- NEVER add skills the candidate does not have\n- Preserve all company names, titles, dates, locations, education exactly\n- Do NOT use em-dashes or unicode special characters. Use regular hyphens (-) and ASCII only\n- Preserve **bold** formatting (double asterisks) from the original bullets. For reformulated bullets, wrap the strongest metric or achievement in **bold** (e.g. **40,000+ new clients**, **reduced error rates by 30%**). Each bullet should have at most one bold highlight\n- VERIFICATION: every reformulated bullet must trace to the original resume. If you cannot trace it, leave the original unchanged.\n\nRules for suggested_bullets[] (gap-fillers - DIFFERENT from main bullets):\n- For each experience entry, generate 1-2 PLAUSIBLE STAR-format bullets that cover JD keywords/skills no existing bullet in this role covers\n- These MAY invent realistic, believable facts/metrics that someone in this role/title at this company at this seniority would credibly have done\n- Specifically target keywords from the JD that no existing bullet mentions\n- Use STAR format: strong action verb, context, concrete (possibly invented) metric or outcome\n- The user reviews these in a diff modal and accepts/rejects each - they know suggestions are speculative gap-fillers\n- Wrap the strongest metric in **bold** (one per bullet)\n- Skip a role entirely if no JD keyword gap exists for it\n\nResume:\n{resume_json}\n\nJob Description:\n{job_description}\n\nReturn ONLY this JSON:\n{\"summary\": \"rewritten summary\", \"experience\": [{\"company\": \"unchanged\", \"title\": \"unchanged\", \"location\": \"unchanged\", \"date\": \"unchanged\", \"description\": \"unchanged or null\", \"bullets\": [\"reformulated or unchanged bullet from existing content\"], \"suggested_bullets\": [\"plausible gap-filler covering missing JD keyword\"]}], \"skills\": {\"reordered label\": \"reordered value\"}}", "Editable resume tailoring LLM prompt template"),
    "persona_tailor_prompt": ("Tailor a FOCUSED resume from this rich candidate profile, targeted at the job description below.\n\nThe candidate profile is a deep pool - most roles have many bullets. SELECT only the strongest aligned with the JD; drop the rest.\n\nRules for MAIN bullets[]:\n- Rewrite the summary to target this specific role (2-4 sentences, lead with the most relevant strength)\n- For each experience entry: SELECT only 3-5 bullets (max 6 for the most senior/recent role) that best match JD keywords and required skills\n- Reformulate each selected bullet to use the JD's exact vocabulary where possible\n- Reorder skills to prioritize JD-relevant ones first; cap at 6 categories\n- Do NOT invent new experience, skills, or facts in the main bullets. Only reframe existing content from the candidate profile\n- NEVER add skills the candidate does not have\n- Preserve all company names, titles, dates, locations, education exactly\n- Do NOT use em-dashes or unicode special characters. Use regular hyphens (-) and ASCII only\n- Preserve **bold** formatting. For reformulated bullets, wrap the strongest metric in **bold** (one per bullet)\n- VERIFICATION: every selected/reformulated bullet must be traceable to the candidate profile\n\nRules for suggested_bullets[] (gap-fillers - DIFFERENT from main bullets):\n- For each experience entry, generate 1-2 PLAUSIBLE STAR-format bullets that cover JD keywords/skills no main bullet (selected from the pool) covers\n- These MAY invent realistic, believable facts/metrics that someone in this role at this company at this seniority would credibly have done\n- Specifically target JD keywords that no main bullet mentions\n- STAR format: strong action verb, context, concrete (possibly invented) metric or outcome\n- The user reviews these in a diff modal and accepts/rejects each\n- Wrap the strongest metric in **bold** (one per bullet)\n- Skip a role if no JD keyword gap exists\n\nCandidate Profile:\n{resume_json}\n\nJob Description:\n{job_description}\n\nReturn ONLY this JSON:\n{\"summary\": \"rewritten summary\", \"experience\": [{\"company\": \"unchanged\", \"title\": \"unchanged\", \"location\": \"unchanged\", \"date\": \"unchanged\", \"description\": \"unchanged or null\", \"bullets\": [\"selected + reformulated bullet from candidate profile\"], \"suggested_bullets\": [\"plausible gap-filler covering missing JD keyword\"]}], \"skills\": {\"reordered label\": \"reordered value\"}}", "Editable Persona tailoring LLM prompt template - used when base_resume_id='persona' to constrain bullet selection from the rich pool"),
    "cover_letter_llm_provider": ("", "LLM provider for cover-letter generation (empty = use primary llm_provider)"),
    "cover_letter_llm_model": ("", "LLM model for cover-letter generation (empty = use primary llm_model)"),
    "cover_letter_llm_api_key": ("", "API key for cover-letter LLM provider"),
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
        "jk",
        # Search-context noise (career page filters that leak into job hrefs):
        "categories", "cities", "locations", "departments", "teams", "regions", "country", "category",
    ]), "URL query params stripped before dedup hashing — tracking/referral noise"),
    "autofill_llm_provider": ("", "LLM provider for application autofill (empty = use primary llm_provider)"),
    "autofill_llm_model": ("", "LLM model for application autofill (empty = use primary llm_model)"),
    "autofill_default_length": ("250", "Default target character length for autofill answers when a field has no maxlength"),
    "autofill_decline_self_id": ("true", "When on, diversity self-ID questions not covered by the persona (pronouns, marital status, etc.) auto-select 'I prefer not to answer' instead of being left blank"),
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
        "ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS target_job_id UUID",
        # Add the missing FK constraint for existing DBs where ADD COLUMN didn't emit REFERENCES.
        # Idempotent via DROP ... IF EXISTS. Mirrors the llm_call_log pattern above.
        "ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS job_runs_target_job_id_fkey",
        "ALTER TABLE job_runs ADD CONSTRAINT job_runs_target_job_id_fkey FOREIGN KEY (target_job_id) REFERENCES jobs(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_job_runs_target_job_id ON job_runs(target_job_id)",
        """ALTER TABLE companies ADD COLUMN IF NOT EXISTS selected_resume_ids JSONB DEFAULT '[]'::jsonb""",
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
          CROSS JOIN LATERAL jsonb_array_elements_text(co.selected_cv_ids) AS cid_str(val)
          JOIN cvs cv ON cv.id::text = cid_str.val
          JOIN resumes r ON r.name = cv.version AND r.is_base = TRUE
         GROUP BY co.id
      ) AS translated
     WHERE c.id = translated.cid
       AND (c.selected_resume_ids IS NULL OR c.selected_resume_ids = '[]'::jsonb);
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
        # Task 11: drop the legacy cvs table — Resume + Persona is the new world.
        # Idempotent: subsequent restarts no-op once the table is gone.
        "DROP TABLE IF EXISTS cvs",
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
    removed_keys = [
        "followup_reminder_days",
        "h1b_exclusion_phrases",
        "language_exclude_phrases",
        "default_cv_id",
        # Orphaned 2026-06: seeded but read by no code. max_jobs_per_scrape
        # promised a per-run cap nothing enforced (sources use results_wanted /
        # max_pages); company_domains/ats_domains were a retired Gmail-detection design.
        "max_jobs_per_scrape",
        "company_domains",
        "ats_domains",
        # 2026-07: openai_compat provider removed — these endpoints were only for it
        "llm_base_url",
        "llm_fallback_base_url",
        # 2026-08: structured-autofill on/off + trigger live in the extension popup,
        # not server settings — they're per-browser preferences.
        "autofill_structured_enabled",
        "autofill_structured_trigger",
    ]
    for key in removed_keys:
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            db.delete(row)
    db.commit()


def migrate_cv_terminology(db):
    """Rename the user-facing word 'CV'/'CVs' -> 'Resume'/'Resumes' in editable
    prompt-text settings, preserving user edits.

    Word-boundary matching leaves the functional template tokens intact
    (CV_NAMES_HERE / best_cv / CV_NAME are not \\bCV\\b matches). Idempotent.
    """
    import re
    for key in ("scoring_rubric",):
        row = db.query(Setting).filter(Setting.key == key).first()
        if not row or not row.value:
            continue
        new = re.sub(r"\bCVs\b", "Resumes", row.value)
        new = re.sub(r"\bCV\b", "Resume", new)
        if new != row.value:
            row.value = new
    db.commit()


def migrate_llm_settings(db):
    """One-shot migrations for the 2026-07 model-list refresh + openai_compat removal.

    - Refresh non-custom entries in llm_models_list to the current DEFAULT_SETTINGS
      list (preserving user-added custom entries; openai_compat entries are dropped
      even if custom — the provider no longer exists).
    - Re-point any provider setting still on openai_compat to openai.
    - Rename the dated claude-haiku-4-5-20251001 model setting values to the alias.
    """
    # Additive seed: default models are offered ONCE (tracked in llm_seeded_models).
    # After that the user's list is authoritative — deleting a default keeps it gone
    # across restarts, while genuinely-new defaults still propagate to existing installs.
    row = db.query(Setting).filter(Setting.key == "llm_models_list").first()
    seen_row = db.query(Setting).filter(Setting.key == "llm_seeded_models").first()
    if seen_row is None:
        seen_row = Setting(key="llm_seeded_models", value="[]",
                           description="Internal: default model keys already offered, so user deletions persist across restarts")
        db.add(seen_row)
    if row and row.value:
        try:
            current = json.loads(row.value)
        except (ValueError, TypeError):
            current = []
        current = [m for m in current if m.get("provider") != "openai_compat"]
        default_list = json.loads(DEFAULT_SETTINGS["llm_models_list"][0])
        try:
            seen = set(json.loads(seen_row.value or "[]"))
        except (ValueError, TypeError):
            seen = set()
        mkey = lambda m: f'{m.get("provider")}|{m.get("model")}'
        have = {mkey(m) for m in current}
        for d in default_list:
            dk = mkey(d)
            if dk not in seen and dk not in have:  # new default the user never removed
                current.append(d)
                have.add(dk)
            seen.add(dk)
        seen_row.value = json.dumps(sorted(seen))
        row.value = json.dumps(current)

    provider_keys = ["llm_provider", "llm_fallback_provider", "email_llm_provider",
                     "cv_tailor_llm_provider", "cover_letter_llm_provider", "autofill_llm_provider",
                     "scoring_llm_provider"]
    for key in provider_keys:
        r = db.query(Setting).filter(Setting.key == key).first()
        if r and r.value == "openai_compat":
            r.value = "openai"

    model_keys = ["llm_model", "llm_fallback_model", "email_llm_model",
                  "cv_tailor_llm_model", "cover_letter_llm_model", "autofill_llm_model",
                  "scoring_llm_model"]
    for key in model_keys:
        r = db.query(Setting).filter(Setting.key == key).first()
        if r and r.value == "claude-haiku-4-5-20251001":
            r.value = "claude-haiku-4-5"

    db.commit()


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

def seed_searches(db):
    """Seed default searches if none exist (except LinkedIn Extension which is always ensured)."""
    existing_modes = {s.search_mode for s in db.query(Search).all()}
    for s in SEED_SEARCHES:
        if s["search_mode"] not in existing_modes:
            db.add(Search(**s))
    # Idempotent rename: the linkedin_extension search was originally seeded as
    # "LinkedIn Extension"; after the Extension/Extension-LI split it should read
    # "Extension LI" so the UI labels match. Self-heal here so fresh DB clones
    # (where the manual rename never ran) end up consistent.
    legacy = db.query(Search).filter(
        Search.search_mode == "linkedin_extension",
        Search.name == "LinkedIn Extension",
    ).first()
    if legacy:
        legacy.name = "Extension LI"
    db.commit()


def seed_mock_resume(db):
    """Seed a mock base Resume for demonstration. Sets it as default Resume for all companies.

    Idempotent: bails if any base Resume already exists. (Replaces the legacy
    seed_mock_cv from before Task 11 dropped the cvs table.)
    """
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

    # Set as default Resume for scoring
    default_row = db.query(Setting).filter(Setting.key == "default_resume_id").first()
    if default_row:
        default_row.value = str(resume.id)
    db.commit()

    # Pre-select this Resume for all seeded companies
    for company in db.query(Company).all():
        company.selected_resume_ids = [str(resume.id)]
    db.commit()

    logger.info("Seeded mock resume 'Sample PM'")


def seed_persona(db):
    """Ensure the singleton Persona (id=1) exists with empty nodes."""
    from backend.models.db import Persona
    existing = db.query(Persona).filter(Persona.id == 1).first()
    if existing:
        return
    p = Persona(
        id=1,
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
    logger.info("Persona singleton (id=1) seeded with empty nodes")


def migrate_h1b_to_visa_cache(db):
    """One-time: copy legacy companies.h1b_* into the visa_cache table, then drop
    those columns. Idempotent — no-op once the columns are gone (fresh installs
    never have them). Postgres only for the DROP; SQLite/tests skip via detection."""
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
    """Merge newly-added canonical keys into the editable autofill dictionaries.

    autofill_field_patterns / autofill_option_synonyms are add-only user-editable
    settings, so seed_settings never touches them once they exist. When new answer
    keys ship (age_range, transgender, sexual_orientation, …) their default label
    synonyms and option synonyms must be merged in without clobbering the user's
    edits: only top-level keys the stored dict is missing are added.
    """
    for setting_key in ("autofill_field_patterns", "autofill_option_synonyms"):
        row = db.query(Setting).filter(Setting.key == setting_key).first()
        if not row:
            continue
        default_json = DEFAULT_SETTINGS.get(setting_key, ("{}", ""))[0]
        try:
            defaults = json.loads(default_json)
            stored = json.loads(row.value or "{}")
        except (ValueError, TypeError):
            continue
        changed = False
        for k, v in defaults.items():
            if k not in stored:
                stored[k] = v
                changed = True
        if changed:
            row.value = json.dumps(stored)
    db.commit()


def run_seeds():
    db = SessionLocal()
    try:
        run_migrations(db)
        seed_settings(db)
        migrate_autofill_dicts(db)
        seed_companies(db)
        seed_h1b_slugs(db)
        seed_searches(db)
        seed_mock_resume(db)
        seed_persona(db)
        cleanup_removed_settings(db)
        migrate_llm_settings(db)
        migrate_cv_terminology(db)
        migrate_h1b_to_visa_cache(db)
    finally:
        db.close()
