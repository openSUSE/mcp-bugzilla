"""
This is an MCP server for bugzilla which provides a few helpful
functions to assist the LLMs with required context

Author: Sai Karthik <kskarthik@disroot.org>
License: Apache 2.0
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

import httpx
from httpx_retries import RetryTransport


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


class Bugzilla:
    """Async Bugzilla API client"""

    def __init__(self, url: str, api_key: str, use_auth_header: bool = False):
        self.base_url = url.rstrip("/")
        self.api_url = f"{self.base_url}/rest"
        self.api_key = api_key
        params = {}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if use_auth_header:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            params["api_key"] = self.api_key
        # We'll use a single client for the instance
        self.client = httpx.AsyncClient(
            base_url=self.api_url,
            params=params,
            timeout=30.0,
            headers=headers,
            transport=RetryTransport(),
        )

    async def close(self):
        await self.client.aclose()

    @property
    def params(self) -> dict[str, Any]:
        """Return params (mainly for read access if needed externally)"""
        return {"api_key": self.api_key}

    async def server_version(self) -> str:
        """Fetch bugzilla server version"""
        try:
            r = await self.client.get("/version")
            r.raise_for_status()
            return r.json()["version"]

        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise

        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

    async def bugzilla_info(self) -> dict[str, Any]:
        """Fetch comprehensive bugzilla server information:
        it returns url, version, extensions, timezone, time and parameters for the current user in a dictionary
        """
        try:
            # Fetch everything concurrently
            version_r, extensions_r, time_r, parameters_r = await asyncio.gather(
                self.client.get("/version"),
                self.client.get("/extensions"),
                self.client.get("/time"),
                self.client.get("/parameters"),
            )

            # Raise for status on all
            for r in [version_r, extensions_r, time_r, parameters_r]:
                r.raise_for_status()

            # Combine results
            version_data = version_r.json()
            extensions_data = extensions_r.json()
            time_data = time_r.json()
            parameters_data = parameters_r.json()

            result = {
                "url": self.base_url,
                "version": version_data.get("version"),
                "extensions": extensions_data.get("extensions", {}),
                "timezone": time_data.get("tz_name"),
                "time": time_data.get("web_time"),
                "parameters": parameters_data.get("parameters", {}),
            }
            mcp_log.info(f"[BZ-RES] Retrieved bugzilla server info from {self.base_url}")
            return result

        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

    async def bug_info(self, ids: set[int]) -> dict[str, Any]:
        """Get information about a given bug or list of bugs"""

        if len(ids) == 1:
            url = f"/bug/{next(iter(ids))}"
            params = {}
        else:
            url = "/bug"
            params = {"id": ",".join(str(i) for i in ids)}

        mcp_log.info(f"[BZ-REQ] GET {self.api_url}{url} params={params}")

        try:
            r = await self.client.get(url, params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        envelope = r.json()
        bugs = envelope.get("bugs", [])
        mcp_log.info(f"[BZ-RES] Retrieved {len(bugs)} bugs")
        mcp_log.debug(f"[BZ-RES] {envelope}")
        return envelope

    async def bug_history(
        self, bug_id: int, new_since: Optional[datetime] = None
    ) -> list[dict[str, Any]]:
        """Get history of a bug"""
        url = f"/bug/{bug_id}/history"
        params = {}
        if new_since:
            params["new_since"] = new_since.strftime("%Y-%m-%dT%H:%M:%SZ")

        mcp_log.info(f"[BZ-REQ] GET {self.api_url}{url} params={params}")

        try:
            r = await self.client.get(url, params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        data = r.json().get("bugs", [])
        history = data[0].get("history", []) if data else []
        mcp_log.info(f"[BZ-RES] Found {len(history)} history items")
        mcp_log.debug(f"[BZ-RES] {history}")
        return history

    async def bug_comments(
        self, bug_id: int, new_since: Optional[datetime] = None
    ) -> list[dict[str, Any]]:
        """Get comments of a bug"""
        url = f"/bug/{bug_id}/comment"
        params = {}
        if new_since:
            params["new_since"] = new_since.strftime("%Y-%m-%dT%H:%M:%SZ")

        mcp_log.info(f"[BZ-REQ] GET {self.api_url}{url} params={params}")

        try:
            r = await self.client.get(url, params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
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
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        data = r.json()
        mcp_log.info("[BZ-RES] Comment added successfully")
        mcp_log.debug(f"[BZ-RES] {data}")
        return data

    async def quicksearch(
        self, query: str, status: str, include_fields: str, limit: int, offset: int
    ) -> dict[str, Any]:
        """Perform a quicksearch"""
        # Quicksearch isn't a direct REST endpoint usually, but /bug with quicksearch param works

        params = {
            "quicksearch": status + " " + query,
            "include_fields": include_fields,
            "limit": limit,
            "offset": offset,
            "order": "relevance",
        }

        mcp_log.info(f"[BZ-REQ] GET {self.api_url}/bug params={params}")

        try:
            r = await self.client.get("/bug", params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        envelope = r.json()
        bugs = envelope.get("bugs", [])
        mcp_log.info(f"[BZ-RES] Found {len(bugs)} bugs")
        return envelope

    async def update_bug(
        self, bug_id: int, updates: dict[str, Any], comment: str = ""
    ) -> dict[str, Any]:
        """Update bug fields. Optionally add a comment with the update."""
        payload = updates.copy()
        if comment:
            payload["comment"] = {"body": comment}

        url = f"/bug/{bug_id}"
        mcp_log.info(f"[BZ-REQ] PUT {self.api_url}{url} json={payload}")

        try:
            r = await self.client.put(url, json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        data = r.json()
        mcp_log.info("[BZ-RES] Bug updated successfully")
        mcp_log.debug(f"[BZ-RES] {data}")
        return data
