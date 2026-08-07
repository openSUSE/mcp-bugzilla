# Agents

This document describes common development tasks for the `mcp-bugzilla` project.

## Project Overview

`mcp-bugzilla` is a Python-based MCP (Model Context Protocol) server that bridges AI clients with Bugzilla instances via the Bugzilla REST API. It is built on [fastmcp](https://github.com/jlowin/fastmcp) and uses `httpx` for HTTP communication.

- **Entry point**: `src/mcp_bugzilla/__init__.py` → `main()`
- **MCP tools/prompts**: `src/mcp_bugzilla/server.py`
- **Bugzilla REST client** (`Bugzilla` class): `src/mcp_bugzilla/lib_bugzilla.py` — single source of truth for all Bugzilla API interactions
- **General utilities** (logging, helpers): `src/mcp_bugzilla/mcp_utils.py`
  - `mcp_utils.py` lazily re-exports `Bugzilla` and `BugzillaAPIError` from `lib_bugzilla.py` for backward compatibility — prefer importing directly from `lib_bugzilla`
- **Tests**: `tests/`
  - `test_cli.py` — CLI argument parsing
  - `test_lib_bugzilla.py` — Bugzilla REST client methods (mocked HTTP with `respx`)
  - `test_server.py` — MCP tool functions (with `AsyncMock` client)
  - `test_transport.py` — MCP transport layer (stdio / HTTP)

## Setup

```bash
uv sync
```

## Running the Server

```bash
uv run mcp-bugzilla --bugzilla-server https://bugzilla.example.com
```

Optional flags:

| Flag | Description |
|------|-------------|
| `--bugzilla-server` | Bugzilla server URL (required; env: `BUGZILLA_SERVER`) |
| `--host` | Listen address (default: `127.0.0.1`) |
| `--port` | Listen port (default: `8000`) |
| `--mcp-auth-header` | Header name for client API key (disabled by default; env: `MCP_AUTH_HEADER`) |
| `--bugzilla-api-key` | Static Bugzilla API key; if omitted access is anonymous (env: `BUGZILLA_API_KEY`) |
| `--bugzilla-auth-mode` | How to authenticate with Bugzilla: `query` (default) or `bearer` for `Authorization: Bearer` (env: `BUGZILLA_AUTH_MODE`) |
| `--read-only` | Disable all write tools |

**Deprecated flags** (still work but log a warning — migrate to the replacements above):

| Deprecated Flag | Replacement |
|-----------------|-------------|
| `--api-key-header` / `MCP_API_KEY_HEADER` | `--mcp-auth-header` / `MCP_AUTH_HEADER` |
| `--api-key` | `--bugzilla-api-key` / `BUGZILLA_API_KEY` |
| `--use-auth-header` | `--bugzilla-auth-mode bearer` |

## Running Tests

```bash
uv run pytest
```

- All *.py must be linted / formatted with ruff whenever they are modified:
  - `uv run ruff check` — lint
  - `uv run ruff format --check` — format
- Tests use `respx` to mock HTTP calls and `pytest-asyncio` for async test support.

## Adding a New Tool

1. Open `src/mcp_bugzilla/server.py`.
2. Define a new async function decorated with `@mcp.tool()`.
3. Add a method to the `Bugzilla` client class in `lib_bugzilla.py` for the authenticated REST call — use the pre-authenticated `self.client` and follow existing methods like `bug_info` / `update_bug` (including their `httpx` error handling) — then call it from the tool.
4. Raise `ToolError` on Bugzilla API errors.
5. Add tests: the client method in `tests/test_lib_bugzilla.py` (mock HTTP with `respx`), and the tool in `tests/test_server.py` (with an `AsyncMock` client).
6. Update relevant documentation wherever applicable

## Disabling Tools at Runtime

Set the `MCP_BUGZILLA_DISABLED_METHODS` environment variable to a comma-separated list of tool names:

```bash
export MCP_BUGZILLA_DISABLED_METHODS=add_comment,update_bug_status
```

Combined with `--read-only` to restrict to a specific read-only subset.

## Authentication Flow

- Clients (http transport) send a Bugzilla API key in an HTTP header (only enabled when `--mcp-auth-header` or `MCP_AUTH_HEADER` is explicitly configured).
- For stdio transport, the key comes from `--bugzilla-api-key` / `BUGZILLA_API_KEY`.
- If no non-empty key is found from any source, access is **anonymous** (no credentials sent to Bugzilla).
- When a key is present, the server forwards it to Bugzilla either as:
  - `?api_key=...` query parameter (`--bugzilla-auth-mode query`, default), or
  - `Authorization: Bearer <KEY>` header (`--bugzilla-auth-mode bearer`, required for Red Hat Bugzilla).

## Docker / Podman

Build:
```bash
docker build -t mcp-bugzilla .
```

Run:
```bash
docker run -p 8000:8000 \
  -e BUGZILLA_SERVER=https://bugzilla.example.com \
  mcp-bugzilla \
  --bugzilla-server https://bugzilla.example.com \
  --host 0.0.0.0 \
  --port 8000
```

## Publishing a New Release

### For Humans

1. Pull latest git changes and run `uv sync`
2. Bump project version with `uv version --bump` (e.g., `--bump minor`)
3. Create a new branch for the release
4. Add entry to `CHANGELOG.md` using `git diff` since the previous tag
5. Open a PR and merge
6. Tag and push: `git tag vX.Y.Z && git push --tags`

### For AI Agents

When asked to publish a release:
- Infer the version bump (patch/minor/major) from commit activity since the latest tag
- Confirm the proposed version with the user before bumping
- Follow the steps above

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP server framework |
| `httpx-retries` | HTTP client with retry support for Bugzilla REST API calls |
| `pytest` + `pytest-asyncio` | Test runner |
| `respx` | Mock HTTP requests in tests |
