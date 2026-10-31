# Legal Disclaimer

## 1. Nature of the Project

JobNavigator is a local, open-source tool -- NOT a hosted service. It runs entirely on your own infrastructure. The maintainers have no visibility into, control over, or responsibility for how the tool is used after download.

## 2. Third-Party Platforms

JobNavigator can interact with job boards, career pages, and job platforms including but not limited to LinkedIn, Indeed, Glassdoor, ZipRecruiter, Jobright.ai, CaribbeanJobs.com, TrulyRemoteWork.com, Behance, Hollylist, Wana Create, Dribbble, ArtStation, Work With Indies, Himalayas, Eluta, Apify, Greenhouse, Lever, Workday, Ashby, and others.

- **Users must comply with the Terms of Service of every platform they interact with.**
- Some features (LinkedIn Personal scraping, LinkedIn Extension import, Jobright.ai recommendations, the Apify search mode, the CaribbeanJobs.com search mode, the Creative boards search mode, the Eluta search mode) may violate the respective platform's Terms of Service. CaribbeanJobs.com puts its pages behind a Cloudflare bot check; JobNavigator does not try to pass it, and a run from a challenged network fails with that reason.
- The Creative boards search mode reads Behance, Hollylist, Wana Create, Dribbble, ArtStation and Work With Indies. Behance, Hollylist and Wana Create publish the APIs it reads for their own sites, not for other clients, and Behance challenges automated visitors. ArtStation and Work With Indies forbid scraping in their terms.
- The Eluta search mode reads the RSS search of Eluta.ca. Eluta's robots.txt disallows that search, and its terms forbid storing its content.
- Himalayas allows its public API on condition that applicants apply through its job link and that jobs are credited to Himalayas. The Himalayas search mode keeps that link as the job's link and shows Himalayas as the job's source. Keep both if you pass these jobs on.
- TrulyRemoteWork.com invites this kind of reading: it publishes its listings for machines (`llms.txt`, `llms-full.txt` and a Markdown twin of each job page) and signals `Content-Signal: ai-train=no, search=yes, ai-input=yes`. It asks that its content not be used to train models and that clients cache responses and respect `Cache-Control`. JobNavigator reads only those published files, caches the listing as long as the board's `Cache-Control` allows, reads each job's page once (again only after a failed read), keeps the jobs in your own database and sends a description to your own LLM only as input for scoring, tailoring and letters, never for training.
- The Apify search mode runs third-party actors from the Apify Store that read LinkedIn, Indeed, Glassdoor and other job boards on your behalf. Those actors are written and run by others, on Apify's servers, under your own Apify account: Apify's terms and the terms of every platform an actor reads apply to you, and Apify bills each run to your account, per result. JobNavigator caps every run but does not choose your plan or your spending limit.
- Each of these features is opt-in: nothing runs until you create a search of that mode, and where a platform needs a login or an API token (LinkedIn, Jobright.ai, Apify), only the credentials you enter yourself are used. CaribbeanJobs.com, TrulyRemoteWork.com, the Creative boards, Himalayas and Eluta take no credentials.
- Do not use this tool to spam employers, overwhelm ATS systems, or submit mass applications.
- Any consequences from ToS violations -- including IP bans, account restrictions, or legal action from platforms -- are **solely the responsibility of the user**.
- The maintainers do not encourage or endorse the violation of any platform's Terms of Service.

## 3. Data Privacy

- All personal data (resumes, credentials, job history) is stored locally in your PostgreSQL database.
- No analytics, telemetry, or usage data is collected by the maintainers.
- Credentials for third-party services are stored in your local database settings table. You are responsible for securing your deployment.
- The maintainers are not a Data Controller or Data Processor under GDPR or any other privacy regulation.

## 4. AI Model Behavior

JobNavigator uses LLM providers (Claude, OpenAI, Ollama, etc.) for CV scoring, email classification, and resume tailoring.

- AI outputs are recommendations, not professional career advice.
- AI models may hallucinate skills, experience, or qualifications. Always verify AI-generated content before using it in applications.
- The maintainers are not responsible for employment outcomes, rejected applications, or any other consequences resulting from AI-generated content.

## 5. Acceptable Use

**Acceptable:**
- Personal job search automation
- Evaluating job offers against your resume
- Generating tailored resumes for specific roles
- Tracking your application pipeline
- Scanning public career pages for new listings

**Not acceptable:**
- Auto-submitting applications without human review
- Scraping platforms at scale beyond personal use
- Selling or redistributing scraped data
- Creating fake accounts for scraping purposes
- Submitting unverified AI-generated content as your own work

## 6. Indemnification

By using this software, you agree to indemnify, defend, and hold harmless the authors, contributors, and any affiliated parties from and against any and all claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising from your use of this software, your violation of these terms, or your violation of any third-party terms of service.

## 7. Warranty Disclaimer

This software is provided under the MIT License "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability arising from the use of this software.

## 8. Changes

This disclaimer may be updated at any time. Continued use of the software constitutes acceptance of any changes.
