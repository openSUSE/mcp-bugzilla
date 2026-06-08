# src/mcp_bugzilla/__init__.py

import argparse
import os
import sys

from . import server
from .mcp_utils import mcp_log


def main():
    parser = argparse.ArgumentParser(
        prog="mcp-bugzilla", description="MCP server for Bugzilla interaction."
    )
    parser.add_argument(
        "--bugzilla-server",
        type=str,
        default=os.getenv("BUGZILLA_SERVER"),
        help="Base URL of the Bugzilla server (e.g., 'https://bugzilla.example.com'). Environment variable BUGZILLA_SERVER is used if argument is not provided.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host address for the MCP server to listen on. Defaults to 127.0.0.1 or MCP_HOST environment variable.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Port for the MCP server to listen on, Defaults to 8000 or MCP_PORT environment variable.",
    )
    parser.add_argument(
        "--api-key-header",
        type=str,
        default=os.getenv("MCP_API_KEY_HEADER", "ApiKey"),
        help="HTTP header for clients to send the Bugzilla API key. Defaults to 'ApiKey' or MCP_API_KEY_HEADER environment variable.",
    )

    parser.add_argument(
        "--use-auth-header",
        action="store_true",
        help="Use Authorization: Bearer header instead of api_key query parameter (required for some Bugzilla instances)",
    )

    parser.add_argument(
        "--read-only",
        action="store_true",
        default=os.getenv("MCP_READ_ONLY", "false").lower() == "true",
        help="Disables all methods which modify the state of the bug. Environment variable MCP_READ_ONLY=true can also be used.",
    )

    parser.add_argument(
        "--transport",
        type=str,
        choices=["http", "stdio"],
        default=os.getenv("MCP_TRANSPORT", "http"),
        help="Transport for the MCP server: 'http' (default) or 'stdio'. Environment variable MCP_TRANSPORT can also be used.",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("BUGZILLA_API_KEY"),
        help="Bugzilla API key. Required for --transport stdio (no HTTP headers exist there). Environment variable BUGZILLA_API_KEY can also be used. Ignored for --transport http (clients send the key per-request via the API key header).",
    )
    args = parser.parse_args()

    # The default behavior of argparse with os.getenv already handles the priority:
    # CLI argument > Environment Variable > Hardcoded default in os.getenv (if provided)

    if args.bugzilla_server is None:
        mcp_log.critical(
            "Error: --bugzilla-server argument or BUGZILLA_SERVER environment variable must be set. Exiting."
        )
        sys.exit(1)

    # Stdio transport has no HTTP request scope, so --host/--port are meaningless
    # and the API key must be provided up-front (env var or CLI flag).
    # We sniff sys.argv because argparse can't natively tell a default value from
    # an explicit pass (env-var defaults muddy the comparison further).
    if args.transport == "stdio":
        explicit_host_or_port = any(
            tok == "--host"
            or tok == "--port"
            or tok.startswith("--host=")
            or tok.startswith("--port=")
            for tok in sys.argv[1:]
        )
        if explicit_host_or_port:
            parser.error("--host/--port are not valid with --transport stdio")
        if not args.api_key:
            parser.error(
                "--transport stdio requires --api-key or the BUGZILLA_API_KEY environment variable"
            )
    elif args.transport == "http" and args.api_key:
        # In http mode the server takes the API key from each client's per-request
        # header; the startup-time --api-key / BUGZILLA_API_KEY is unused. Warn so
        # the user cleans the config and doesn't think they're authenticating.
        mcp_log.warning(
            "--api-key / BUGZILLA_API_KEY is set but ignored with --transport http "
            "(clients send the key per-request via the API key header). "
            "Unset it to clean the config."
        )

    server.cli_args = args
    server.start()


if __name__ == "__main__":
    main()
