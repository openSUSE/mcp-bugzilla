"""Tests for transport selection and per-transport API key sourcing."""

from argparse import Namespace
from unittest.mock import patch

import pytest

from mcp_bugzilla import server


def _base_args(**overrides):
    """Build a Namespace with all attrs server.start() / get_bz() may read."""
    defaults = dict(
        bugzilla_server="https://bugzilla.example.com",
        host="127.0.0.1",
        port=8000,
        # New primary auth args
        mcp_auth_header="ApiKey",
        bugzilla_api_key=None,
        bugzilla_auth_mode="query",
        # Deprecated args kept for backward compatibility
        api_key_header=None,
        use_auth_header=False,
        api_key=None,
        read_only=False,
        transport="http",
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def test_stdio_transport_invokes_mcp_run_stdio():
    server.cli_args = _base_args(transport="stdio", bugzilla_api_key="k")
    with patch.object(server.mcp, "run") as mock_run:
        server.start()
    mock_run.assert_called_once_with(transport="stdio", show_banner=False)


def test_http_transport_unchanged():
    server.cli_args = _base_args(transport="http")
    with patch.object(server.mcp, "run") as mock_run:
        server.start()
    mock_run.assert_called_once_with(
        transport="http", host="127.0.0.1", port=8000, show_banner=False
    )


@pytest.mark.asyncio
async def test_get_bz_uses_cli_api_key_in_stdio_mode():
    server.cli_args = _base_args(transport="stdio", bugzilla_api_key="from-cli")
    server.base_url = "https://bugzilla.example.com"

    async with server.get_bz(headers={}) as bz:
        assert bz.api_key == "from-cli"


@pytest.mark.asyncio
async def test_get_bz_uses_header_in_http_mode():
    server.cli_args = _base_args(transport="http")
    server.base_url = "https://bugzilla.example.com"

    async with server.get_bz(headers={"apikey": "from-header"}) as bz:
        assert bz.api_key == "from-header"


@pytest.mark.asyncio
async def test_get_bz_falls_back_to_static_key_in_http_mode():
    """When the per-request header is absent, fall back to --bugzilla-api-key."""
    server.cli_args = _base_args(transport="http", bugzilla_api_key="static-key")
    server.base_url = "https://bugzilla.example.com"

    async with server.get_bz(headers={}) as bz:
        assert bz.api_key == "static-key"


@pytest.mark.asyncio
async def test_get_bz_anonymous_http_mode():
    """No header and no static key → anonymous (empty api_key)."""
    server.cli_args = _base_args(transport="http")
    server.base_url = "https://bugzilla.example.com"

    async with server.get_bz(headers={}) as bz:
        assert bz.api_key == ""


@pytest.mark.asyncio
async def test_get_bz_anonymous_stdio_mode():
    """No --bugzilla-api-key in stdio → anonymous (empty api_key)."""
    server.cli_args = _base_args(transport="stdio", bugzilla_api_key=None)
    server.base_url = "https://bugzilla.example.com"

    async with server.get_bz(headers={}) as bz:
        assert bz.api_key == ""


@pytest.mark.asyncio
async def test_get_bz_bearer_auth_mode():
    """--bugzilla-auth-mode bearer is passed through to the Bugzilla client."""
    server.cli_args = _base_args(transport="stdio", bugzilla_api_key="k", bugzilla_auth_mode="bearer")
    server.base_url = "https://bugzilla.example.com"

    async with server.get_bz(headers={}) as bz:
        assert bz.api_key == "k"
        # bearer mode: Authorization header set, no api_key query param
        assert "Authorization" in bz.client.headers
        assert "api_key" not in bz.client.params
