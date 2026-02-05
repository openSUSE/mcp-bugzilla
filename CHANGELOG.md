# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),

## [Unreleased]

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
  *   **Status Badge**: Added a "Tests" workflow status badge to the `README.md`.
  *   **Dependencies**: Updated `pyproject.toml` to include `pytest`, `pytest-asyncio`, and `respx` as development dependencies.
