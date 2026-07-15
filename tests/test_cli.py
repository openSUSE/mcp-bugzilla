"""Tests for CLI argument validation in mcp_bugzilla.main()."""

import logging
from unittest.mock import patch

import pytest

from mcp_bugzilla import main


@pytest.fixture
def captured_mcp_log(caplog):
    """Attach caplog's handler to the bugzilla-mcp logger.

    The mcp_log logger has propagate=False (see mcp_utils.py), so caplog's
    default root-level capture does not see its records. We add caplog.handler
    directly for the duration of the test.
    """
    logger = logging.getLogger("bugzilla-mcp")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.WARNING, logger="bugzilla-mcp")
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


def _run_main(monkeypatch, argv, env=None):
    """Run main() with patched argv/env and a no-op server.start()."""
    monkeypatch.setattr("sys.argv", ["mcp-bugzilla", *argv])
    # Clear env vars that argparse defaults read from, then apply test-specific ones.
    for var in (
        "BUGZILLA_SERVER",
        "BUGZILLA_API_KEY",
        "MCP_HOST",
        "MCP_PORT",
        "MCP_TRANSPORT",
        "MCP_READ_ONLY",
        "MCP_AUTH_HEADER",
        "MCP_API_KEY_HEADER",
        "BUGZILLA_AUTH_MODE",
    ):
        monkeypatch.delenv(var, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)

    with patch("mcp_bugzilla.server.start") as mock_start:
        main()
    return mock_start


# ---------------------------------------------------------------------------
# Deprecated --api-key behaviour
# ---------------------------------------------------------------------------

def test_deprecated_api_key_http_warns_and_starts(monkeypatch, captured_mcp_log):
    """Using the deprecated --api-key flag must emit a deprecation warning."""
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "http",
            "--api-key",
            "legacy-key",
        ],
    )
    mock_start.assert_called_once()
    warnings = [r for r in captured_mcp_log.records if r.levelno == logging.WARNING]
    assert any("--api-key is deprecated" in r.message for r in warnings), (
        f"Expected --api-key deprecation warning, got: {[r.message for r in warnings]}"
    )


def test_new_bugzilla_api_key_http_no_warning(monkeypatch, captured_mcp_log):
    """Using the new --bugzilla-api-key must NOT emit a deprecation warning."""
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "http",
            "--bugzilla-api-key",
            "new-key",
        ],
    )
    mock_start.assert_called_once()
    deprecation_warnings = [
        r for r in captured_mcp_log.records
        if r.levelno == logging.WARNING and "deprecated" in r.message.lower()
    ]
    assert deprecation_warnings == [], (
        f"Did not expect deprecation warning, got: {[r.message for r in deprecation_warnings]}"
    )


def test_deprecated_api_key_header_warns(monkeypatch, captured_mcp_log):
    """Using the deprecated --api-key-header flag must emit a deprecation warning."""
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "http",
            "--api-key-header",
            "X-Legacy-Key",
        ],
    )
    mock_start.assert_called_once()
    warnings = [r for r in captured_mcp_log.records if r.levelno == logging.WARNING]
    assert any("--api-key-header" in r.message and "deprecated" in r.message for r in warnings), (
        f"Expected --api-key-header deprecation warning, got: {[r.message for r in warnings]}"
    )


def test_deprecated_use_auth_header_warns(monkeypatch, captured_mcp_log):
    """Using the deprecated --use-auth-header flag must emit a deprecation warning."""
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "http",
            "--use-auth-header",
        ],
    )
    mock_start.assert_called_once()
    warnings = [r for r in captured_mcp_log.records if r.levelno == logging.WARNING]
    assert any("--use-auth-header" in r.message and "deprecated" in r.message for r in warnings), (
        f"Expected --use-auth-header deprecation warning, got: {[r.message for r in warnings]}"
    )


def test_deprecated_env_api_key_header_warns(monkeypatch, captured_mcp_log):
    """MCP_API_KEY_HEADER env var (deprecated) must also emit a deprecation warning."""
    mock_start = _run_main(
        monkeypatch,
        ["--bugzilla-server", "https://bugzilla.example.com", "--transport", "http"],
        env={"MCP_API_KEY_HEADER": "X-Legacy-Key"},
    )
    mock_start.assert_called_once()
    warnings = [r for r in captured_mcp_log.records if r.levelno == logging.WARNING]
    assert any("--api-key-header" in r.message and "deprecated" in r.message for r in warnings), (
        f"Expected MCP_API_KEY_HEADER deprecation warning, got: {[r.message for r in warnings]}"
    )


# ---------------------------------------------------------------------------
# Anonymous access (no key required)
# ---------------------------------------------------------------------------

def test_http_transport_without_any_key_starts(monkeypatch, captured_mcp_log):
    """http transport without any API key must start (anonymous access)."""
    mock_start = _run_main(
        monkeypatch,
        ["--bugzilla-server", "https://bugzilla.example.com", "--transport", "http"],
    )
    mock_start.assert_called_once()


def test_stdio_transport_without_api_key_starts(monkeypatch, captured_mcp_log):
    """stdio transport without any API key must start (anonymous access)."""
    mock_start = _run_main(
        monkeypatch,
        ["--bugzilla-server", "https://bugzilla.example.com", "--transport", "stdio"],
    )
    mock_start.assert_called_once()


# ---------------------------------------------------------------------------
# stdio + --host/--port rejection
# ---------------------------------------------------------------------------

def test_stdio_transport_with_host_exits(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "mcp-bugzilla",
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "stdio",
            "--host",
            "0.0.0.0",
        ],
    )
    for var in ("BUGZILLA_API_KEY", "MCP_TRANSPORT", "MCP_AUTH_HEADER", "MCP_API_KEY_HEADER"):
        monkeypatch.delenv(var, raising=False)

    with patch("mcp_bugzilla.server.start") as mock_start, pytest.raises(SystemExit):
        main()
    mock_start.assert_not_called()


def test_mcp_auth_header_defaults_to_none_when_omitted(monkeypatch):
    """If --mcp-auth-header is omitted and env var is not set, it should default to None."""
    from mcp_bugzilla import server
    _run_main(
        monkeypatch,
        ["--bugzilla-server", "https://bugzilla.example.com", "--transport", "http"],
    )
    assert server.cli_args.mcp_auth_header is None


def test_invalid_bugzilla_auth_mode_env_exits(monkeypatch, captured_mcp_log):
    """If BUGZILLA_AUTH_MODE env var has an invalid value, main() must log a critical error and exit."""
    with pytest.raises(SystemExit) as exc_info:
        _run_main(
            monkeypatch,
            ["--bugzilla-server", "https://bugzilla.example.com", "--transport", "http"],
            env={"BUGZILLA_AUTH_MODE": "invalid_mode"},
        )
    assert exc_info.value.code == 1
    critical_logs = [r for r in captured_mcp_log.records if r.levelno == logging.CRITICAL]
    assert any("Invalid --bugzilla-auth-mode" in r.message for r in critical_logs), (
        f"Expected critical log for invalid bugzilla-auth-mode, got: {[r.message for r in critical_logs]}"
    )

