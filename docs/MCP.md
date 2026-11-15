# MCP server

JobNavigator has an MCP server at `<dashboard>/api/mcp`. An MCP client, for example Claude Code, can read your jobs, searches, applications, resumes, cover letters and scrape logs through it.

Most tools only read. Six tools change data: `update_jobs`, `mark_job_applied`, `tailor_resume`, `generate_cover_letter`, `generate_for_jobs` and `stop_batch`. An MCP client asks before it calls a tool that is not read-only.

## Authentication

The MCP server uses the same two headers as the REST API. It has no access of its own.

| Header | Value | Where to get it |
|---|---|---|
| `X-API-Key` | The install password | Settings › Advanced |
| `X-Account-Token` | The API token of your account | Settings › Accounts › **API token** |

A client inside a signed-in dashboard tab can use its session cookies in place of the two headers.

With one account, `X-Account-Token` is optional. With two or more accounts it is required, and each tool returns only the data of that account. The token is valid for a year. A PIN change ends it.

## Claude Code

Put both values in environment variables first, so that they stay out of the shell history. Then add the server. The variable syntax depends on the shell.

PowerShell:

```powershell
claude mcp add --scope user --transport http jobnavigator https://your-host/api/mcp --header "X-API-Key: $env:JN_API_KEY" --header "X-Account-Token: $env:JN_ACCOUNT_TOKEN"
```

bash or zsh:

```bash
claude mcp add --scope user --transport http jobnavigator https://your-host/api/mcp --header "X-API-Key: ${JN_API_KEY}" --header "X-Account-Token: ${JN_ACCOUNT_TOKEN}"
```

The shell replaces the two variables. Claude Code then stores the values in its user configuration file on your computer. Do not use `--scope project`: that scope writes the values to `.mcp.json` in the repository.

Check the result with `claude mcp get jobnavigator`: each header must show a value. A variable that is not set, or the bash form in PowerShell, stores an empty header. The server then answers 401, and an older install whose proxy has no rule for `/.well-known/oauth-*` makes the client report `JSON Parse error: Unrecognized token`. Remove the server (`claude mcp remove jobnavigator`) and add it again. Start a new Claude Code session after a change.

Then ask Claude Code, for example: "Which searches failed in their last runs?"

## Tools

| Tool | Returns |
|---|---|
| `get_stats` | Counts of jobs and of applications by status |
| `list_jobs` | Jobs with filters (status, company, score, search, source, location, title), without the long text fields |
| `get_job` | One job with its description and scoring report |
| `list_searches` | Searches with their configuration and last run |
| `list_applications` | Applications, most recently updated first |
| `list_scheduled_jobs` | Scheduler jobs with their next run time |
| `list_active_runs` | Background runs in progress |
| `list_run_history` | Background runs, newest first |
| `get_scrape_log` | Scrape history, optionally errors or 0-result runs only |
| `list_failing_sources` | Companies and searches whose last scrapes all failed |
| `get_activity_log` | Activity log entries |
| `list_runners` | State of the CLI runner containers |
| `list_in_flight` | Runs in progress per job (tailor, cover letter, scoring) |
| `get_run` | One background run: status, the error text of a failure, and the ids of what it created (`meta.created`) |
| `list_resumes` | Resumes without their content; filters for base or tailored, one job, creation time, count |
| `list_cover_letters` | Cover letters, optionally for one job |
| `get_resume` | One resume with its content |
| `get_cover_letter` | One cover letter with its text |
| `get_persona` | The Persona of the account: contact data and career facts |
| `get_batch` | A batch of `generate_for_jobs`: status, counts, and the jobs of one state |

Write tools:

| Tool | Does |
|---|---|
| `update_jobs` | Sets `status`, `saved` or `seen` on many jobs. The reply has the previous values of each job, for an undo |
| `mark_job_applied` | Sets one job to `applied` and creates its application, as the dashboard does |
| `tailor_resume` | Starts a background run that tailors a base resume for a job. It replaces the tailored copy that the job already has |
| `generate_cover_letter` | Starts a background run that writes a cover letter from a resume for a job |
| `generate_for_jobs` | Starts a batch on the server: a tailored resume and a cover letter for each job of a list |
| `stop_batch` | Stops a batch: no more jobs start, the jobs in progress end |

Each tool is one request to the REST API with your headers: a `GET` for a read tool, the dashboard's own `POST` for a write tool. A tool therefore shows and does exactly what the same API call shows and does.

### Batches

For more than one job, use `generate_for_jobs`. The queue is on the server, so the batch does not depend on the client: a closed session or a reloaded page does not stop it.

- A batch takes 200 jobs at most. One batch runs at a time for an account; a second one gets a 409.
- Each job goes through three runs, one after the other: the tailor, the scoring run that follows it, the cover letter. The server works on 2 jobs at a time (Settings › `tailoring_max_concurrent`), so a batch has at most 2 LLM calls in progress. Runs that you start outside the batch are not counted.
- The tailor replaces the tailored copy that the job has. A job that has a cover letter gets that letter rewritten.
- `get_batch` gives the counts for each state (`queued`, `tailoring`, `scoring`, `cover_letter`, `done`, `failed`, `cancelled`). Give `state` to get the jobs of that state: a `done` job has `resume_id` and `cover_letter_id`, a `failed` job has `step` and `error`.
- A failed job does not stop the batch. A backend restart ends the batch (`status` `failed`, error `Process restarted`); start a new batch with the jobs that are not `done`.

The REST form is `POST /api/generate-batches`, `GET /api/generate-batches/{id}` and `POST /api/generate-batches/{id}/stop`.

### Single runs

`tailor_resume` and `generate_cover_letter` use the LLM of your model settings. Start at most 2 runs at a time, then wait with `get_run`. A completed tailor run names the new copy and the scoring run that follows it (`meta.created.resume_id`, `meta.created.chained_run_id`); a completed cover-letter run names the letter (`meta.created.cover_letter_id`). A run that a backend restart ended is `failed` with the error `Process restarted`.

Keep replies small: `list_jobs` takes `fields` (the row keys to keep) for long lists, and `list_resumes` takes `job_id`, `created_after` and `limit`. `list_searches` leaves out the title and company filter lists unless you give `brief=false`. `list_scheduled_jobs` leaves out the rows of searches and companies with their own interval unless you give `overrides=true`. A scoring run follows each tailor (Settings › Résumé & tailoring) and uses the runner too.

There is no tool for the company list: with its scrape configuration it is too large for one reply (about 300 KB for 200 companies). `list_failing_sources` names the companies whose scrapes fail.

The server does not save files. To save a PDF, download `GET /api/resumes/{id}/pdf` or `GET /api/cover-letters/{id}/pdf` on your computer with the same two headers.

## Notes

- The transport is streamable HTTP, stateless, with JSON replies. The path is under `/api/`, so a reverse proxy that already passes `/api/*` needs no change for it. The bundled Caddy also answers `/.well-known/oauth-*` with 404: an MCP client reads those paths after a 401, and the dashboard page there hides the real error. Give your own proxy the same rule.
- The server needs the `mcp` Python package, which is part of the backend image. After an upgrade from source, rebuild the backend image. Until then the backend starts without the MCP server and writes `MCP server is off` to its log.
