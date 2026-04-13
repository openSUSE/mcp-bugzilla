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
| `--api-key-header` | Header name for client API key (default: `ApiKey`) |
| `--use-auth-header` | Send API key as `Authorization: Bearer` to Bugzilla (for Red Hat Bugzilla etc.) |
| `--read-only` | Disable all write tools |

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

## Disabling Tools at Runtime

Set the `MCP_BUGZILLA_DISABLED_METHODS` environment variable to a comma-separated list of tool names:

```bash
export MCP_BUGZILLA_DISABLED_METHODS=add_comment,update_bug_status
```

Combined with `--read-only` to restrict to a specific read-only subset.

## Authentication Flow

- Clients send a Bugzilla API key in an HTTP header (default header name: `ApiKey`).
- The server extracts this key per-request and forwards it to Bugzilla either as:
  - `?api_key=...` query parameter (default), or
  - `Authorization: Bearer ...` header (`--use-auth-header`).

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

1. Bump `version` in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Tag the commit and push.
4. Run `publish-image.sh` to push the Docker image to Docker Hub.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP server framework |
| `httpx-retries` | HTTP client with retry support for Bugzilla REST API calls |
| `pytest` + `pytest-asyncio` | Test runner |
| `respx` | Mock HTTP requests in tests |
