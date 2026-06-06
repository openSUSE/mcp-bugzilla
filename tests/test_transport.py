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
        api_key_header="ApiKey",
        use_auth_header=False,
        read_only=False,
        transport="http",
        api_key=None,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def test_stdio_transport_invokes_mcp_run_stdio():
    server.cli_args = _base_args(transport="stdio", api_key="k")
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
    server.cli_args = _base_args(transport="stdio", api_key="from-cli")
    # Set base_url the way start() would; we skip start() to avoid mcp.run().
    server.base_url = "https://bugzilla.example.com"

    # In stdio mode, headers are irrelevant; pass an empty dict.
    async with server.get_bz(headers={}) as bz:
        assert bz.api_key == "from-cli"


@pytest.mark.asyncio
async def test_get_bz_uses_header_in_http_mode():
    server.cli_args = _base_args(transport="http")
    server.base_url = "https://bugzilla.example.com"

    async with server.get_bz(headers={"apikey": "from-header"}) as bz:
        assert bz.api_key == "from-header"


@pytest.mark.asyncio
async def test_get_bz_raises_in_stdio_mode_without_key():
    from fastmcp.exceptions import ValidationError

    server.cli_args = _base_args(transport="stdio", api_key=None)
    server.base_url = "https://bugzilla.example.com"

    with pytest.raises(ValidationError):
        async with server.get_bz(headers={}):
            pass
