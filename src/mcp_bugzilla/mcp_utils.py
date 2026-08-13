"""
MCP utilities for the Bugzilla MCP server.

Provides logging configuration, attachment helpers, and re-exports the
``Bugzilla`` client from :mod:`lib_bugzilla` for backward compatibility.

Author: Sai Karthik <kskarthik@disroot.org>
License: Apache 2.0
"""

import logging
import os
import re

# Re-export Bugzilla and BugzillaAPIError for backward compatibility.
# Lazily imported to avoid circular dependencies — lib_bugzilla imports
# mcp_log from here, so we can't import from lib_bugzilla at module level.


def __getattr__(name: str):
    """Lazy-import Bugzilla / BugzillaAPIError to break the circular import."""
    if name in ("Bugzilla", "BugzillaAPIError"):
        from .lib_bugzilla import Bugzilla, BugzillaAPIError

        if name == "Bugzilla":
            return Bugzilla
        return BugzillaAPIError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Logging configuration
class ColorFormatter(logging.Formatter):
    GREY = "\x1b[38;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    CYAN = "\x1b[36;20m"
    BLUE = "\x1b[34;20m"
    GREEN = "\x1b[32;20m"

    FORMAT = "[%(levelname)s]: %(message)s"

    def format(self, record):
        log_fmt = self.FORMAT
        if isinstance(record.msg, str):
            if "[LLM-REQ]" in record.msg or "[LLM-RES]" in record.msg:
                log_fmt = self.CYAN + self.FORMAT + self.RESET
            elif "[BZ-REQ]" in record.msg or "[BZ-RES]" in record.msg:
                log_fmt = self.GREEN + self.FORMAT + self.RESET

        if record.levelno >= logging.ERROR:
            log_fmt = self.RED + self.FORMAT + self.RESET

        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


handler = logging.StreamHandler()
handler.setFormatter(ColorFormatter())

mcp_log = logging.getLogger("bugzilla-mcp")
mcp_log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
mcp_log.addHandler(handler)
mcp_log.propagate = False


# Content types whose payload is textual and safe to return inline as decoded text.
_TEXTUAL_CONTENT_TYPES = {
    "application/json",
    "application/xml",
    "application/x-sh",
    "application/javascript",
    "application/x-yaml",
    "image/svg+xml",
}


def is_textual(content_type: str) -> bool:
    """Whether an attachment's content can be returned inline as decoded text."""
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct.startswith("text/"):
        return True
    if ct in _TEXTUAL_CONTENT_TYPES:
        return True
    if ct.endswith(("+xml", "+json")):
        return True
    return "patch" in ct or "diff" in ct


def safe_filename(name: str | None, attachment_id: int) -> str:
    """Sanitize a Bugzilla-supplied file name for safe use as a path component.

    Strips any directory part and collapses anything outside ``[A-Za-z0-9._-]``
    to ``_`` so a hostile ``file_name`` (e.g. ``../../etc/passwd``) cannot escape
    the target directory.
    """
    base = os.path.basename(name or "").strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._")
    return base or f"attachment-{attachment_id}"
