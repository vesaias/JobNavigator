# ATS Report: Software Engineering Intern, MS, Summer 2027 at Google

## Inputs and Assumptions

- JD source: https://www.google.com/about/careers/applications/jobs/results/95141459539174086, accessed Jul 22, 2026.
- Resume library: `D:\Github\resume\data\facts_master.json`, `D:\Github\ChineseInternetResume\resume-zh_CN.tex`, and dated, de-identified Microsoft evidence in `D:\Github\interview-stories\stories\`.
- Special requirement: incorporate the updated Microsoft internship and tailor it for this Google role.
- Output constraints: English, ATS-safe, one page, standard headings, one column, and application-ready PDF.
- Assumption: the current one-page US resume convention should remain in place.

## Coverage Summary

- Direct: current U.S. M.S. in Computer Science, software development, C++, Java, Python, JavaScript, data structures and algorithms, AI/ML, information retrieval, mobile development, distributed systems, large software systems, testing, and debugging.
- Transferable: analyzing alternatives, automating or operating build/test workflows, supporting team decisions, and technical documentation.
- Adjacent: infrastructure through Docker, build systems, CI/reliability work, and distributed database implementation; web application development through FastAPI and REST APIs.
- Weak: Unix/Linux is plausible from systems work but is not explicit enough in the evidence library for a resume claim.
- Unsupported: confirmed full-time 12-week availability and returning to a degree program after the internship.

## Keyword Use

### Used

- `Master's` / `M.S. in Computer Science`: Education.
- `C++`, `Java`, `Python`, `JavaScript`: Technical Skills and project evidence.
- `Data Structures`, `Algorithms`: Technical Skills, supported by computer science education and systems implementation.
- `AI/ML`, `Information Retrieval`, `mobile`, `Distributed Systems`, `large software systems`: Technical Skills, Microsoft experience, and projects.
- `design`, `test`, `debugging`, `reliability`: Microsoft experience and Technical Skills.

### Omitted or Limited

- `Unix/Linux`: omitted because current sources do not explicitly establish hands-on scope.
- `develop scripts to automate routine tasks`: not claimed as a Microsoft accomplishment; the evidence supports using build automation and scripts, not authoring them.
- `security software development`: omitted; Keychain troubleshooting is adjacent but is not security-product development.
- `available full time for 12 weeks`: omitted from the resume pending user confirmation.

## Requirement Map

| JD requirement | Match | Evidence source | Resume handling | Risk |
| --- | --- | --- | --- | --- |
| Pursuing a Master's in a software-related field | Direct | UC Davis M.S. in CS, Sep 2025-Jun 2027 | Education first | None |
| Software development in two or more general-purpose languages | Direct | ResilientDB, ZhihuRec, RAG project, skills library | Lists C++, Java, Python, and JavaScript | None |
| Data structures or algorithms | Direct | CS education, Raft implementation, local algorithm practice | Exact terms in Technical Skills | Keep only if candidate is comfortable defending them in interview |
| Three or more listed languages | Direct | C++, Java, Python, JavaScript project and skills evidence | Four JD-listed languages near the top | None |
| AI/ML and information retrieval | Direct | RAG and ZhihuRec projects | Exact domain terms and project evidence | Production ML depth is not claimed |
| Mobile application development | Direct | Microsoft 365 Copilot mobile internship | Strongest experience bullet | Work centers on build/test and integration, not feature ownership |
| Distributed systems | Direct | ResilientDB Raft implementation | Two project bullets | Personal/open-source branch, not upstream contribution |
| Developing large software systems | Direct | Microsoft monorepo, 1,500+ build steps, 100+ subprojects | Quantified first experience bullet | Metrics come from de-identified dated work evidence |
| Analyze information and choose solutions | Direct | Microsoft build failure and reliability triage | Second and third experience bullets | Avoid implying sole ownership of the quarantine PR |
| Team collaboration | Direct | Reliability decision and reviewed merge | Three approvals and all checks passing | PR was colleague-led; resume uses `supported`, not `led` |
| Unix/Linux | Weak | Systems work only | Omitted | Ask user for a concrete Linux example if desired |
| Full-time 12-week availability | Unsupported | No confirmed source | Omitted | Confirm in application form |
| Returning to degree after internship | Unsupported | User-confirmed graduation is mid-Jun 2027 | Omitted | Confirm the internship dates; returning to school after the program is not currently supported |

## Special Requirements Applied

- Updated Microsoft internship: replaced generic setup bullets with evidence of large-system onboarding, controlled build debugging, and data-driven reliability triage.
- Google alignment: emphasized four listed languages, algorithms, AI/ML, information retrieval, mobile development, distributed systems, and large software systems.
- One page: omitted the lower-signal Keychain and toolchain-version stories and kept the three Microsoft outcomes most relevant to the JD.

## Truthfulness Risks

- `facts_master.json` is stale and still describes the Microsoft role as incoming; the later current resume and dated work evidence support `Jun 2026 - Present` and the new bullets.
- Confirm that `1,500+ steps`, `100+ subprojects`, `four stale test frameworks`, `three approvals`, and `all checks passing` are acceptable to disclose externally.
- The resume does not claim that the candidate authored automation scripts, owned the colleague-led PR, or contributed the ResilientDB branch upstream.
- Expected graduation is mid-Jun 2027. Because this is a Summer 2027 internship, confirm the exact program dates; returning to a degree program after the internship remains unsupported.

## Manual Edits Recommended

- Confirm full-time availability for the 12-week internship in the application form.
- Use `Expected Jun 2027` consistently in the resume and application; change it only if the official academic timeline changes.
- Upload a current English transcript; the JD explicitly requests one.
- Do not add work authorization or sponsorship language unless the candidate confirms the exact wording.
