"""
This is an MCP server for bugzilla which provides a few helpful
functions to assist the LLMs with required context

Author: Sai Karthik <kskarthik@disroot.org>
License: Apache 2.0
"""

import logging
import os
from contextvars import ContextVar
from typing import Any, Optional

import httpx

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
            if "[LLM-REQ]" in record.msg:
                log_fmt = self.CYAN + self.FORMAT + self.RESET
            elif "[LLM-RES]" in record.msg:
                log_fmt = self.CYAN + self.FORMAT + self.RESET
            elif "[BZ-REQ]" in record.msg:
                log_fmt = self.GREEN + self.FORMAT + self.RESET
            elif "[BZ-RES]" in record.msg:
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

# ContextVar to hold the Bugzilla client instance for the current context
bugzilla_client: ContextVar[Optional["Bugzilla"]] = ContextVar("bugzilla_client", default=None)


class Bugzilla:
    """Async Bugzilla API client"""

    def __init__(self, url: str, api_key: str):
        self.base_url = url.rstrip("/")
        self.api_url = f"{self.base_url}/rest"
        self.api_key = api_key
        # We'll use a single client for the instance
        self.client = httpx.AsyncClient(
            base_url=self.api_url,
            params={"api_key": self.api_key},
            timeout=30.0,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

    async def close(self):
        await self.client.aclose()
    
    @property
    def params(self) -> dict[str, Any]:
        """Return params (mainly for read access if needed externally)"""
        return {"api_key": self.api_key}

    async def bug_info(self, bug_id: int) -> dict[str, Any]:
        """Get information about a given bug"""
        # Note: self.client has base_url set to .../rest
        # So we request /bug/{id} relative to that.
        url = f"/bug/{bug_id}" 
        mcp_log.info(f"[BZ-REQ] GET {self.api_url}{url}")

        try:
            r = await self.client.get(url)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        data = r.json().get("bugs", [{}])[0]
        mcp_log.info(f"[BZ-RES] Found bug {bug_id}")
        mcp_log.debug(f"[BZ-RES] {data}")
        return data

    async def bug_comments(self, bug_id: int) -> list[dict[str, Any]]:
        """Get comments of a bug"""
        url = f"/bug/{bug_id}/comment"
        mcp_log.info(f"[BZ-REQ] GET {self.api_url}{url}")

        try:
            r = await self.client.get(url)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        # The response structure is {"bugs": {"<id>": {"comments": [...]}}}
        data = r.json().get("bugs", {}).get(str(bug_id), {}).get("comments", [])
        mcp_log.info(f"[BZ-RES] Found {len(data)} comments")
        mcp_log.debug(f"[BZ-RES] {data}")
        return data

    async def add_comment(
        self, bug_id: int, comment: str, is_private: bool
    ) -> dict[str, int]:
        """Add a comment to bug, which can optionally be private"""
        payload = {"comment": comment, "is_private": is_private}
        url = f"/bug/{bug_id}/comment"
        mcp_log.info(f"[BZ-REQ] POST {self.api_url}{url} json={payload}")

        try:
            r = await self.client.post(url, json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        data = r.json()
        mcp_log.info("[BZ-RES] Comment added successfully")
        mcp_log.debug(f"[BZ-RES] {data}")
        return data

    async def quicksearch(self, query: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Perform a quicksearch"""
        # Quicksearch isn't a direct REST endpoint usually, but /bug with quicksearch param works
        params = {
            "quicksearch": query,
            "limit": limit,
            "offset": offset,
        }
        # Merge with existing params (api_key)
        
        mcp_log.info(f"[BZ-REQ] GET {self.api_url}/bug params={params}")
        
        try:
            r = await self.client.get("/bug", params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}")
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        bugs = r.json().get("bugs", [])
        mcp_log.info(f"[BZ-RES] Found {len(bugs)} bugs")
        return bugs
