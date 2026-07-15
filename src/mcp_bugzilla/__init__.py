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

    # --- Inbound auth: client -> MCP ---
    parser.add_argument(
        "--mcp-auth-header",
        type=str,
        default=os.getenv("MCP_AUTH_HEADER", "ApiKey"),
        help="HTTP header name that clients use to send the Bugzilla API key to this MCP server (http transport only). Defaults to 'ApiKey' or MCP_AUTH_HEADER environment variable. Replaces --api-key-header.",
    )

    # --- Outbound auth: MCP -> Bugzilla ---
    parser.add_argument(
        "--bugzilla-api-key",
        type=str,
        default=os.getenv("BUGZILLA_API_KEY"),
        help="Bugzilla API key. If omitted (and not provided per-request via --mcp-auth-header for http transport), Bugzilla access is anonymous. For --transport stdio this is the only source of the key. Environment variable BUGZILLA_API_KEY can also be used. Replaces --api-key.",
    )
    parser.add_argument(
        "--bugzilla-auth-mode",
        type=str,
        choices=["query", "bearer"],
        default=os.getenv("BUGZILLA_AUTH_MODE", "query"),
        help="How to authenticate with Bugzilla: 'query' (default) sends the API key as the api_key query parameter; 'bearer' sends it as an Authorization: Bearer <KEY> header (required for some Bugzilla instances such as Red Hat Bugzilla). Environment variable BUGZILLA_AUTH_MODE can also be used. Replaces --use-auth-header.",
    )

    # --- Deprecated args kept for backward compatibility ---
    # TODO: Remove deprecated args when deprecation period expires.
    parser.add_argument(
        "--api-key-header",
        type=str,
        default=os.getenv("MCP_API_KEY_HEADER"),
        help="[DEPRECATED] Use --mcp-auth-header / MCP_AUTH_HEADER instead.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="[DEPRECATED] Use --bugzilla-api-key / BUGZILLA_API_KEY instead.",
    )
    parser.add_argument(
        "--use-auth-header",
        action="store_true",
        help="[DEPRECATED] Use --bugzilla-auth-mode bearer instead.",
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
        "--download-dir",
        type=str,
        default=os.getenv("BUGZILLA_DOWNLOAD_DIR"),
        help="Directory where download_attachment writes binary/oversized attachments. "
        "Defaults to <tmpdir>/mcp-bugzilla or the BUGZILLA_DOWNLOAD_DIR environment variable.",
    )

    args = parser.parse_args()

    # The default behavior of argparse with os.getenv already handles the priority:
    # CLI argument > Environment Variable > Hardcoded default in os.getenv (if provided)

    if args.bugzilla_server is None:
        mcp_log.critical(
            "Error: --bugzilla-server argument or BUGZILLA_SERVER environment variable must be set. Exiting."
        )
        sys.exit(1)

    # TODO: Remove deprecated arg handling when deprecation period expires.
    # Map deprecated args to their replacements, with a visible warning.
    _new_auth_header_set = os.getenv("MCP_AUTH_HEADER") or any(
        tok == "--mcp-auth-header" or tok.startswith("--mcp-auth-header=")
        for tok in sys.argv[1:]
    )
    if args.api_key_header is not None:
        mcp_log.warning(
            "--api-key-header / MCP_API_KEY_HEADER is deprecated; "
            "use --mcp-auth-header / MCP_AUTH_HEADER instead."
        )
        if not _new_auth_header_set:
            args.mcp_auth_header = args.api_key_header

    if args.api_key is not None:
        mcp_log.warning(
            "--api-key is deprecated; "
            "use --bugzilla-api-key / BUGZILLA_API_KEY instead."
        )
        if args.bugzilla_api_key is None:
            args.bugzilla_api_key = args.api_key

    if args.use_auth_header:
        mcp_log.warning(
            "--use-auth-header is deprecated; "
            "use --bugzilla-auth-mode bearer instead."
        )
        if args.bugzilla_auth_mode == "query":
            args.bugzilla_auth_mode = "bearer"

    # Stdio transport has no HTTP request scope, so --host/--port are meaningless.
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

    server.cli_args = args
    server.start()


if __name__ == "__main__":
    main()
