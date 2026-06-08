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
        "MCP_API_KEY_HEADER",
    ):
        monkeypatch.delenv(var, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)

    with patch("mcp_bugzilla.server.start") as mock_start:
        main()
    return mock_start


def test_http_transport_with_api_key_warns_but_starts(monkeypatch, captured_mcp_log):
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "http",
            "--api-key",
            "leftover-key",
        ],
    )
    mock_start.assert_called_once()
    warnings = [r for r in captured_mcp_log.records if r.levelno == logging.WARNING]
    assert any("ignored with --transport http" in r.message for r in warnings), (
        f"Expected http+api_key warning, got: {[r.message for r in warnings]}"
    )


def test_http_transport_without_api_key_does_not_warn(monkeypatch, captured_mcp_log):
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "http",
        ],
    )
    mock_start.assert_called_once()
    warnings = [
        r
        for r in captured_mcp_log.records
        if r.levelno == logging.WARNING and "ignored with --transport http" in r.message
    ]
    assert warnings == [], (
        f"Did not expect a warning, got: {[r.message for r in warnings]}"
    )


def test_http_transport_with_env_api_key_warns(monkeypatch, captured_mcp_log):
    """The warning must also fire when api_key comes from BUGZILLA_API_KEY env var."""
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "http",
        ],
        env={"BUGZILLA_API_KEY": "from-env"},
    )
    mock_start.assert_called_once()
    warnings = [r for r in captured_mcp_log.records if r.levelno == logging.WARNING]
    assert any("ignored with --transport http" in r.message for r in warnings), (
        f"Expected http+api_key warning, got: {[r.message for r in warnings]}"
    )


def test_stdio_transport_with_api_key_does_not_warn(monkeypatch, captured_mcp_log):
    mock_start = _run_main(
        monkeypatch,
        [
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "stdio",
            "--api-key",
            "k",
        ],
    )
    mock_start.assert_called_once()
    warnings = [
        r
        for r in captured_mcp_log.records
        if r.levelno == logging.WARNING and "ignored with --transport http" in r.message
    ]
    assert warnings == [], (
        f"Did not expect http warning in stdio mode, got: {[r.message for r in warnings]}"
    )


def test_stdio_transport_without_api_key_exits(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "mcp-bugzilla",
            "--bugzilla-server",
            "https://bugzilla.example.com",
            "--transport",
            "stdio",
        ],
    )
    for var in ("BUGZILLA_API_KEY", "MCP_TRANSPORT"):
        monkeypatch.delenv(var, raising=False)

    with patch("mcp_bugzilla.server.start") as mock_start, pytest.raises(SystemExit):
        main()
    mock_start.assert_not_called()
