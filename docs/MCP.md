# MCP server

JobNavigator has an MCP server at `<dashboard>/api/mcp`. An MCP client, for example Claude Code, can read your jobs, searches, companies, applications and scrape logs through it.

The server has read tools only. It cannot change data.

## Authentication

The MCP server uses the same two headers as the REST API. It has no access of its own.

| Header | Value | Where to get it |
|---|---|---|
| `X-API-Key` | The install password | Settings › Advanced |
| `X-Account-Token` | The API token of your account | Settings › Accounts › **API token** |

With one account, `X-Account-Token` is optional. With two or more accounts it is required, and each tool returns only the data of that account. The token is valid for a year. A PIN change ends it.

## Claude Code

Put both values in environment variables first, so that they stay out of the shell history.

```bash
claude mcp add --scope user --transport http jobnavigator https://your-host/api/mcp --header "X-API-Key: ${JN_API_KEY}" --header "X-Account-Token: ${JN_ACCOUNT_TOKEN}"
```

The shell replaces the two variables. Claude Code then stores the values in its user configuration file on your computer. Do not use `--scope project`: that scope writes the values to `.mcp.json` in the repository.

Then ask Claude Code, for example: "Which searches failed in their last runs?"

## Tools

| Tool | Returns |
|---|---|
| `get_stats` | Counts of jobs and of applications by status |
| `list_jobs` | Jobs with filters (status, company, score, search, source, location, title), without the long text fields |
| `get_job` | One job with its description and scoring report |
| `list_searches` | Searches with their configuration and last run |
| `list_companies` | Tracked companies with their scrape configuration |
| `list_applications` | Applications, most recently updated first |
| `list_scheduled_jobs` | Scheduler jobs with their next run time |
| `list_active_runs` | Background runs in progress |
| `list_run_history` | Background runs, newest first |
| `get_scrape_log` | Scrape history, optionally errors or 0-result runs only |
| `list_failing_sources` | Companies and searches whose last scrapes all failed |
| `get_activity_log` | Activity log entries |
| `list_runners` | State of the CLI runner containers |

Each tool is one `GET` on the REST API with your headers, so a tool shows exactly what the same API call shows.

## Notes

- The transport is streamable HTTP, stateless, with JSON replies. The path is under `/api/`, so the bundled Caddy and a reverse proxy that already passes `/api/*` need no change.
- The server needs the `mcp` Python package, which is part of the backend image. After an upgrade from source, rebuild the backend image. Until then the backend starts without the MCP server and writes `MCP server is off` to its log.
