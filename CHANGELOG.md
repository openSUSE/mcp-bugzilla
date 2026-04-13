# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),

## [v0.12.1] - 2026-04-13

### Added
- add `AGENTS.md`

### Fixed
- Clear resolution when reopening bugs from CLOSED/VERIFIED status.

### Chore
- Bump fastmcp from 3.1.1 to 3.2.0
- Bump uv from 0.11.0 to 0.11.6
- Bump cryptography from 46.0.6 to 46.0.7
- Bump pygments from 2.19.2 to 2.20.0

## [v0.12.0] - 2026-03-30

### Added
- `bugzilla_server_info` tool providing comprehensive Bugzilla server details, replacing the `server_url_resource` tool.
- `bug_history` tool to retrieve the change history of a bug.
- `MCP_READ_ONLY` environment variable support for read-only mode.
- `bug_info` now accepts multiple bug IDs (as a set) in a single call.
- `quicksearch` now returns the full response envelope.

### Fixed
- `bug_info` working on a single bug restored.
- Fastmcp banner no longer shown at startup.

### Chore
- Refactor `bug_info` methods and tests to accept a set of bug IDs instead of a list.
- Bump cryptography from 46.0.5 to 46.0.6
- Bump requests from 2.32.5 to 2.33.0
- Bump uv from 0.10.11 to 0.11.0
- Update uv-build requirement

## [v0.11.0]- 2026-03-18

### Added
- `mcp_server_info_resource` now also returns bugzilla server's version
- Add `new_since` parameter to `bug_comments` to filter results by date.
- Add comprehensive write operations to Bugzilla MCP. This fills a significant gap in the original implementation, which only supported `add_comment` for write operations. These additions enable full bug lifecycle management through the MCP interface. New tools added include:
  - `update_bug_status`: Change bug status with proper validation (requires resolution when closing bugs)
  - `assign_bug`: Assign bugs to users with optional comment
  - `update_bug_fields`: Modify priority, severity, and resolution
  - `add_cc_to_bug`: Add email addresses to CC list
  - `mark_as_duplicate`: Properly close bugs as duplicates with both status, resolution, and dupe_of fields
- Add `--read-only` CLI flag to disable tools which can modify status of a bug

### Fixed
- Add missing CLI flag `--use-auth-header`

### Chore
- Bump fastmcp from 3.1.0 to 3.1.1
- Bump uv from 0.10.9 to 0.10.11
- Bump authlib from 1.6.7 to 1.6.9
- Bump pyjwt from 2.11.0 to 2.12.0
- Bump uv from 0.10.7 to 0.10.9
- Bump authlib from 1.6.6 to 1.6.7
- Added tests for new methods

## [v0.10.0] - 2026-03-03

### Added
- Some Bugzilla instances require `Authorization: Bearer` header instead of api_key query parameters. Add CLI flag to support both methods while maintaining backward compatibility. [#14](https://github.com/openSUSE/mcp-bugzilla/pull/14)

- Selectively disable some tools via env `MCP_BUGZILLA_DISABLED_METHODS`. [#13](https://github.com/openSUSE/mcp-bugzilla/pull/13)

### Changed
- All existing resources are converted as tools & renamed for wider mcp client compatibility [#13](https://github.com/openSUSE/mcp-bugzilla/pull/13)

- Container process now runs with a lower user permission for improved security

- Update dependencies

Please refer the README for more info & examples

## [v0.9.0] - 2026-02-05

### Changed
- bugs_quicksearch enhanced
- test and README files reviewed
- change CMD to ENTRYPOINT in Dockerfile

### Fixed
- fixed bug in learn_quicksearch_syntax

## [v0.8.0] - 2026-01-06

### Added

* handle api response failures using `httpx-retries` library 

Several New Improvements by [@SanthoshSiddegowda](https://github.com/SanthoshSiddegowda)
  *   **Async Refactor**: Switched from synchronous `httpx` logic to `httpx.AsyncClient` across `mcp_utils.py` and `server.py`. All MCP tools (`bug_info`, `bug_comments`, etc.) are now `async` functions, allowing for non-blocking concurrent request handling.
  *   **Thread-Safety**: Introduced `contextvars` to manage the `Bugzilla` client instance per request context. This ensures that the server is safe for concurrent use and prevents race conditions with API keys or session state.
  *   **Resource Management**: Implemented proper cleanup logic in the middleware to ensure the HTTP client is closed after every request.
  *   **Unit Tests**: Added a new test suite in `tests/test_mcp_utils.py` covering core functionalities (`bug_info`, `bug_comments`, `add_comment`, `quicksearch`).
  *   **Mocking**: Utilized `respx` to mock external Bugzilla API calls, ensuring tests are fast and deterministic without requiring a live server.
  *   **CI/CD**: Added a GitHub Actions workflow (`.github/workflows/tests.yml`) to automatically run tests on every push and pull request.
  *   **Status Badge**: Added a \"Tests\" workflow status badge to the `README.md`.
  *   **Dependencies**: Updated `pyproject.toml` to include `pytest`, `pytest-asyncio`, and `respx` as development dependencies.
