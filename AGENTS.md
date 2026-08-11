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

## Running Tests

```bash
uv run pytest # unit tests
uv run ruff check # lint
uv run ruff format --check # format
```

- Tests use `respx` to mock HTTP calls and `pytest-asyncio` for async test support.

## Adding a New Tool

1. Open `src/mcp_bugzilla/server.py`.
2. Define a new async function decorated with `@mcp.tool()`.
3. Add a method to the `Bugzilla` client class in `lib_bugzilla.py` for the authenticated REST call — use the pre-authenticated `self.client` and follow existing methods like `bug_info` / `update_bug` (including their `httpx` error handling) — then call it from the tool.
4. Raise `ToolError` on Bugzilla API errors.
5. Add tests: the client method in `tests/test_lib_bugzilla.py` (mock HTTP with `respx`), and the tool in `tests/test_server.py` (with an `AsyncMock` client).
6. Update relevant documentation wherever applicable

## Commit style

- Use atomic commits & follow [conventional commits spec](https://raw.githubusercontent.com/conventional-commits/conventionalcommits.org/refs/heads/master/content/v1.0.0/index.md)
## Publishing a New Release

### For Humans

1. Pull latest git changes and run `uv sync`
2. Bump project version with `uv version --bump` (e.g., `--bump minor`)
3. Create a new branch for the release
4. Add entry to `CHANGELOG.md` using `git diff` since the previous tag
5. Open a PR and merge

### For AI Agents

When asked to publish a release:
- Infer the version bump (patch/minor/major) from commit activity since the latest tag
- Confirm the proposed version with the user before bumping
- Follow the steps above
