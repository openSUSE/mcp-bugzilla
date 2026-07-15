# Agents

This document describes common development tasks for the `mcp-bugzilla` project.

## Project Overview

`mcp-bugzilla` is a Python-based MCP (Model Context Protocol) server that bridges AI clients with Bugzilla instances via the Bugzilla REST API. It is built on [fastmcp](https://github.com/jlowin/fastmcp) and uses `httpx` for HTTP communication.

- **Entry point**: `src/mcp_bugzilla/__init__.py` → `main()`
- **MCP tools/prompts**: `src/mcp_bugzilla/server.py`
- **HTTP utilities**: `src/mcp_bugzilla/mcp_utils.py`
- **Tests**: `tests/`

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
| `--host` | Listen address (default: `127.0.0.1`) |
| `--port` | Listen port (default: `8000`) |
| `--mcp-auth-header` | Header name for client API key (default: `ApiKey`; env: `MCP_AUTH_HEADER`) |
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

Tests use `respx` to mock HTTP calls and `pytest-asyncio` for async test support.

## Adding a New Tool

1. Open `src/mcp_bugzilla/server.py`.
2. Define a new async function decorated with `@mcp.tool()`.
3. Use `make_bugzilla_request()` from `mcp_utils.py` for authenticated Bugzilla REST API calls.
4. Raise `ToolError` on Bugzilla API errors.
5. Add a corresponding test in `tests/test_mcp_utils.py` (or a new test file) using `respx` to mock the HTTP response.
6. update relevant documentation wherever applicable

## Disabling Tools at Runtime

Set the `MCP_BUGZILLA_DISABLED_METHODS` environment variable to a comma-separated list of tool names:

```bash
export MCP_BUGZILLA_DISABLED_METHODS=add_comment,update_bug_status
```

Combined with `--read-only` to restrict to a specific read-only subset.

## Authentication Flow

- Clients (http transport) send a Bugzilla API key in an HTTP header (default header name: `ApiKey`, configurable via `--mcp-auth-header`).
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

1. pull latest git changes & run `uv sync`
2. Bump project version with `uv version --bump` . Guess the version bump based on commit activity since previous git tag & Confirm with user before bumping the version
3. create a new branch for release
4. Add entry to `CHANGELOG.md` listing the changes using `git diff` since latest previous tags as per the existing CHANGELOG format


## Key Dependencies

| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP server framework |
| `httpx-retries` | HTTP client with retry support for Bugzilla REST API calls |
| `pytest` + `pytest-asyncio` | Test runner |
| `respx` | Mock HTTP requests in tests |
