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
        help="Use Authorization: Bearer header instead of api_key query parameter (required for some Bugzilla instances)"
    )

    args = parser.parse_args()

    # The default behavior of argparse with os.getenv already handles the priority:
    # CLI argument > Environment Variable > Hardcoded default in os.getenv (if provided)

    if args.bugzilla_server is None:
        mcp_log.critical(
            "Error: --bugzilla-server argument or BUGZILLA_SERVER environment variable must be set. Exiting."
        )
        sys.exit(1)

    server.cli_args["bugzilla_server"] = args.bugzilla_server
    server.cli_args["host"] = args.host
    server.cli_args["port"] = args.port
    server.cli_args["api_key_header"] = args.api_key_header

    server.start()


if __name__ == "__main__":
    main()
