# Legal Disclaimer

## 1. Nature of the Project

JobNavigator is a local, open-source tool -- NOT a hosted service. It runs entirely on your own infrastructure. The maintainers have no visibility into, control over, or responsibility for how the tool is used after download.

## 2. Third-Party Platforms

JobNavigator can interact with job boards, career pages, and job platforms including but not limited to LinkedIn, Indeed, ZipRecruiter, Jobright.ai, Greenhouse, Lever, Workday, Ashby, and others.

- **Users must comply with the Terms of Service of every platform they interact with.**
- Some features (LinkedIn Personal scraping, LinkedIn Extension import, Jobright.ai recommendations) may violate the respective platform's Terms of Service.
- These features are **disabled by default** and require users to explicitly provide their own credentials to enable them.
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
