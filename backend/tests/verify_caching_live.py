"""Live Anthropic caching verification — not a pytest test, run manually via python -m.

Makes 3 identical `call_llm(..., cached_prefix=...)` calls in quick succession, then
inspects `llm_call_log` to confirm:
  - Call 1: cache_write_tokens > 0 (cache miss, writes the prefix)
  - Calls 2 & 3: cache_read_tokens > 0 (cache hit, reads the prefix ~10x cheaper)

Requirements:
  - backend container running
  - `llm_provider='claude_api'` setting in DB (or env-var ANTHROPIC_API_KEY available as fallback)
  - cached_prefix must be ≥ 1024 tokens for Sonnet/Opus caching

Run inside the backend container:
  docker compose exec -T backend python -m backend.tests.verify_caching_live
"""
import asyncio
import sys


# A synthetic rubric + fake CV blob, long enough to exceed the 1024-token minimum.
# Each call uses IDENTICAL prefix bytes — that's what Anthropic keys the cache on.
CACHED_PREFIX = """You are a senior tech recruiter using the following 5-criteria rubric.
Score each category 0-20. Sum = total 0-100. Be precise and use the rubric language.

CRITERION 1 — Skills Match (0-20): How well do the candidate's listed skills match the
job's required and preferred skills? Consider both technical skills (programming languages,
frameworks, tools) and soft skills (leadership, communication). Weight required > preferred.
Partial match is common; apply 25% credit for adjacent skills (e.g. Java for Kotlin role).
Look for specific terms, not just topic areas. Penalize skill gaps on must-have items.

CRITERION 2 — Experience Level (0-20): Does the candidate's years of experience, role
progression, and scope of responsibility align with the job level? A Senior role wants
5-10 years; Staff 10+; Principal 12+. Judge not just years but depth — mentor role,
architect role, IC at scale. Discount irrelevant years (e.g., years in a different stack).

CRITERION 3 — Domain Fit (0-20): Does the candidate's industry or product domain match?
Fintech looks for fintech; healthtech looks for regulated domains; gaming looks for games.
Adjacent domains (B2B SaaS → B2B SaaS) score higher than unrelated (gaming → fintech).
Consider product type: consumer vs enterprise, marketplace, platform, infra.

CRITERION 4 — Role Alignment (0-20): Is the candidate's current or target role a match?
A PM applying to a PM role scores well; an SWE applying to PM scores lower. Check for
level match (IC ↔ IC, management ↔ management). Factor in recency — "was a PM 5 years ago"
doesn't count as much as "is currently a PM".

CRITERION 5 — Requirements Match (0-20): Are hard requirements met? This is the filter
stage: US work authorization, location or remote, degree, certifications, specific
frameworks. Hard blockers (e.g., "must be in NYC" for a local role) cap this at 5.
Soft requirements can be met partially; hard requirements are binary.

OUTPUT FORMAT: JSON only, no markdown or commentary.
{
  "scores": {"CV_A": <0-100>},
  "best_cv": "CV_A",
  "summary": "<one-sentence overall fit>"
}

CV VERSION 1 — CV_A:
Senior Product Manager with 8 years of experience at Stripe and Airbnb. Led the payments
platform team at Stripe from 0 to $50M ARR. At Airbnb, managed the host onboarding flow
reducing time-to-first-listing by 40%. Strong in SQL, product analytics (Amplitude, Mode),
A/B testing (Optimizely), and cross-functional leadership. Previous experience as a
software engineer in Python and Go for 3 years before pivoting to PM. MBA from Stanford,
BSc in Computer Science from MIT. Speaks English, Spanish, Mandarin. Located in San
Francisco, willing to work hybrid or remote. Authorized to work in the US (US citizen).
Skills: SQL, Python, product analytics, A/B testing, user research, OKRs, roadmapping,
stakeholder management, go-to-market strategy, pricing, technical PM work.

EMPLOYMENT HISTORY IN DETAIL:

STRIPE (2022-present, 2 years). Senior Product Manager, Payments Platform.
- Shipped the v2 of the Payments API, processing $50B annualized volume within 18 months.
- Owned pricing strategy for interchange-plus routing, yielding a 12% margin improvement.
- Led a team of 4 PMs and partnered with 30+ engineers across Infrastructure, Risk, and
  Payouts to ship the new Settlements engine.
- Defined OKRs for the platform team: reliability (99.995% uptime), latency (p95 < 200ms),
  and authorization rate (+1.5% YoY).
- Hired and ramped 3 PMs during a year of heavy scaling.
- Pioneered the use of LLM-assisted requirement triage for the roadmap process.

AIRBNB (2018-2022, 4 years). Product Manager, Supply Growth.
- Owned the host onboarding funnel: reduced time-to-first-listing from 14 days to 8 days.
- Launched the Professional Hosts program, now representing 35% of gross bookings.
- Ran weekly A/B tests on the listing creation flow; shipped 47 experiments over 3 years.
- Launched in 12 new countries; led localization efforts and payment method expansion.
- Moved the host dashboard from legacy PHP to React; partnered closely with engineering.
- Mentored 6 APMs through the APM rotational program.

GOOGLE (2015-2018, 3 years). Software Engineer, YouTube Monetization.
- Built the contextual ad-targeting pipeline using Go + BigQuery, $15M incremental revenue.
- Maintained the YouTube Partner Program classification service: 10k QPS, 3ms p99 latency.
- Reduced spam creator applications by 40% using a Python/TensorFlow classification model.
- Part of the YouTube Ads interview committee; conducted 60+ interviews.

EDUCATION:
- Stanford MBA (2022): Focus on Product Management and Operations. GPA 3.9.
- MIT BSc Computer Science (2015): Summa cum laude, Phi Beta Kappa.

AWARDS & CERTIFICATIONS:
- Pragmatic Marketing Certified (PMC-III), 2020.
- Internal Stripe Impact Award, Q2 2023 (top 5% of all ICs).
- AWS Solutions Architect - Associate, 2017.

PUBLICATIONS:
- "Scaling Host Onboarding at Airbnb" — Product Collective, March 2021.
- "A/B Testing for PMs: 7 Anti-Patterns" — Reforge blog, August 2022.

Skills continued (expanded taxonomy for this test):
- Product: PRDs, roadmapping, stakeholder alignment, OKRs, KPI definition, experimentation
  frameworks, customer discovery, quant/qual research, PRFAQ writing, launch planning.
- Data: SQL (advanced), Python (pandas/numpy), R (intermediate), BigQuery, Snowflake,
  dbt, Looker, Tableau, Mode, Amplitude, Mixpanel, Pendo, Heap, statistical significance.
- Engineering: Go, Python, Java, JavaScript/TypeScript, React, REST API design, GraphQL,
  distributed systems basics, database fundamentals (ACID, BASE, CAP), event-driven systems.
- Domain: Payments (SCA, PCI, interchange, ACH, SEPA, wire, crypto rails), Marketplaces
  (two-sided network effects, trust & safety, fraud), Monetization (ads, subscription).
- Soft: executive communication, conflict resolution, mentorship, public speaking.
"""

PROMPT_TEMPLATE = "JOB DESCRIPTION:\n{job}"

JOBS = [
    # 3 DIFFERENT JD suffixes, but IDENTICAL cached_prefix
    "Senior PM at a Series B fintech. 5+ years product management experience. Remote OK. Competitive salary + equity.",
    "Director of Product, Payments. Lead the monetization team. 10+ years experience, fintech preferred. Based in SF or NYC.",
    "Principal PM, Growth. Own experimentation platform. Heavy A/B testing background. Seattle HQ, hybrid 3 days/week.",
]


async def main():
    # Force module re-import of settings so any cached DB connection sees current values
    from backend.analyzer.llm_client import call_llm

    # Anthropic's docs say 1024-token minimum for Sonnet, but in practice caching only
    # kicks in when the cacheable block is comfortably above that — likely 2000+ tokens.
    # Double the prefix to stay safely past any threshold.
    doubled_prefix = CACHED_PREFIX + "\n\n" + CACHED_PREFIX

    print(f"cached_prefix length: {len(doubled_prefix)} chars (~{len(doubled_prefix) // 4} tokens)")
    if len(doubled_prefix) < 4096:
        print("WARN: cached_prefix likely < 1024 tokens. Caching won't activate.")

    for i, jd in enumerate(JOBS, 1):
        print(f"\n--- Call {i}/3 ---")
        prompt = PROMPT_TEMPLATE.format(job=jd)
        resp = await call_llm(
            prompt=prompt,
            system="Return ONLY JSON. Follow the rubric precisely.",
            max_tokens=300,
            cached_prefix=doubled_prefix,
        )
        usage = resp.get("usage", {})
        print(f"  text (first 100 chars): {resp['text'][:100]!r}")
        print(f"  input_tokens:       {usage.get('input_tokens', 0)}")
        print(f"  output_tokens:      {usage.get('output_tokens', 0)}")
        print(f"  cache_read_tokens:  {usage.get('cache_read_tokens', 0)}")
        print(f"  cache_write_tokens: {usage.get('cache_write_tokens', 0)}")

    print("\nDone. Now run: SELECT purpose, input_tokens, cache_read_tokens, cache_write_tokens FROM llm_call_log;")


if __name__ == "__main__":
    asyncio.run(main())
