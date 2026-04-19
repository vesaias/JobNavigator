# Security

## Reporting a vulnerability

Found a security issue? Please **don't open a public issue**. Instead:

- Use GitHub's [Private Vulnerability Reporting](https://github.com/vesaias/JobNavigator/security/advisories/new) (preferred)
- Or message me via the GitHub profile

I'll acknowledge within a few days. This is a personal project so response isn't 24/7, but I take security seriously.

## Scope

**In scope:**
- Authentication bypass on the dashboard
- Credential leakage (API keys, OAuth tokens, scraper credentials)
- SSRF / XSS / SQL injection
- PII exposure from cached pages, CVs, scoring reports
- Dependency vulnerabilities affecting the running app

**Out of scope:**
- Issues requiring local OS-level compromise
- ToS concerns about scraping third-party sites (see [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md))
- Bugs in upstream libraries (report those upstream)
- Rate-limit or account-ban issues from third-party services

## Supported versions

Only `main` is supported — there are no tagged releases yet. If you're running an older commit, please pull latest first.

## Credentials stored

JobNavigator stores these in the DB `settings` table (redacted in API responses):

- LLM API keys (Anthropic, OpenAI, etc.)
- LinkedIn mock account credentials
- Jobright.ai credentials
- Gmail OAuth refresh token
- Telegram bot token
- Dashboard API key

All are local to your Postgres instance. Treat your DB backups as sensitive — they contain these in plaintext. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md) for broader disclaimers.
