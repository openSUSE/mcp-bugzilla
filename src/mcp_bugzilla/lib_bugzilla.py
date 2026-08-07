"""Async Bugzilla REST API client.

Moved from mcp_utils.py for better modularity.
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
from httpx_retries import RetryTransport

from .mcp_utils import mcp_log


class BugzillaAPIError(Exception):
    """Bugzilla REST API error with code and message."""

    def __init__(self, status_code: int, error: dict[str, Any]):
        self.status_code = status_code
        self.code = error.get("code")
        self.message = error.get("message", "Unknown error")
        super().__init__(
            f"Bugzilla API error {self.code} (HTTP {status_code}): {self.message}"
        )


def _bugzilla_error_body(response: httpx.Response) -> dict[str, Any] | None:
    """Parse Bugzilla error from response body, if present."""
    try:
        body = response.json()
        if isinstance(body, dict) and body.get("error") and "message" in body:
            return body
    except (ValueError, KeyError):
        pass
    return None


class Bugzilla:
    """Async Bugzilla API client"""

    def __init__(self, url: str, api_key: str = "", use_auth_header: bool = False):
        self.base_url = url.rstrip("/")
        self.api_url = f"{self.base_url}/rest"
        self.api_key = api_key
        params = {}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        # Only attach auth credentials when a non-empty key is provided;
        # an empty key means anonymous access (no api_key param or Authorization header).
        if api_key:
            if use_auth_header:
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                params["api_key"] = api_key
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
            mcp_log.info(
                f"[BZ-RES] Retrieved bugzilla server info from {self.base_url}"
            )
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

    async def bug_flags(self, bug_id: int) -> list[dict[str, Any]]:
        """Return the flags currently set on a bug, with their instance ids.

        The default bug view omits flags on some instances (e.g. Red Hat
        Bugzilla), so we request them explicitly via include_fields.
        """
        url = f"/bug/{bug_id}"
        params = {"include_fields": "id,flags"}
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

        bugs = r.json().get("bugs", [])
        flags = bugs[0].get("flags", []) if bugs else []
        mcp_log.info(f"[BZ-RES] Retrieved {len(flags)} flags for bug {bug_id}")
        return flags

    async def bug_history(
        self, bug_id: int, new_since: datetime | None = None
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
        self, bug_id: int, new_since: datetime | None = None
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
        self, query: str, include_fields: str, limit: int, offset: int
    ) -> dict[str, Any]:
        """Perform a quicksearch"""
        # Quicksearch isn't a direct REST endpoint usually, but /bug with quicksearch param works

        params = {
            "quicksearch": query,
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
            if (bz_error := _bugzilla_error_body(e.response)) is not None:
                # Surface structured Bugzilla error (e.g., validation rejection)
                mcp_log.error(
                    f"[BZ-RES] Failed: {e.response.status_code} code={bz_error.get('code')} {bz_error['message']}"
                )
                raise BugzillaAPIError(e.response.status_code, bz_error) from e
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

    async def create_bug(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Create a new bug from the given field mapping.

        Bugzilla requires at least product, component, summary, version and
        description; instances may mandate more. The raw Bugzilla error (e.g.
        a missing required field) is surfaced to the caller.
        """
        url = "/bug"
        mcp_log.info(f"[BZ-REQ] POST {self.api_url}{url} json={fields}")

        try:
            r = await self.client.post(url, json=fields)
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
        mcp_log.info(f"[BZ-RES] Created bug {data.get('id')}")
        mcp_log.debug(f"[BZ-RES] {data}")
        return data

    async def add_attachment(
        self, bug_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Attach a file to a bug. ``payload['data']`` is base64-encoded."""
        url = f"/bug/{bug_id}/attachment"
        # Don't log the (possibly large / binary) base64 blob.
        mcp_log.info(
            f"[BZ-REQ] POST {self.api_url}{url} file_name={payload.get('file_name')!r}"
        )

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
        mcp_log.info(f"[BZ-RES] Attachment(s) {data.get('ids')} added to bug {bug_id}")
        mcp_log.debug(f"[BZ-RES] {data}")
        return data

    async def list_attachments(self, bug_id: int) -> list[dict[str, Any]]:
        """List a bug's attachments (metadata only, base64 ``data`` excluded)."""
        url = f"/bug/{bug_id}/attachment"
        mcp_log.info(f"[BZ-REQ] GET {self.api_url}{url} exclude_fields=data")

        try:
            r = await self.client.get(url, params={"exclude_fields": "data"})
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        # /bug/{id}/attachment returns {"bugs": {"<bug_id>": [ {att}, ... ]}}
        attachments = r.json().get("bugs", {}).get(str(bug_id), [])
        mcp_log.info(f"[BZ-RES] Bug {bug_id} has {len(attachments)} attachment(s)")
        return attachments

    async def get_attachment(self, attachment_id: int) -> dict[str, Any]:
        """Fetch a single attachment, including its base64-encoded ``data``."""
        url = f"/bug/attachment/{attachment_id}"
        # Don't log the (possibly large / binary) base64 blob in the response.
        mcp_log.info(f"[BZ-REQ] GET {self.api_url}{url}")

        try:
            r = await self.client.get(url)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            mcp_log.error(
                f"[BZ-RES] Failed: {e.response.status_code} {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            mcp_log.error(f"[BZ-RES] Network Error: {e}")
            raise

        # /bug/attachment/{id} returns {"attachments": {"<attachment_id>": {att}}}
        attachment = r.json().get("attachments", {}).get(str(attachment_id))
        if attachment is None:
            raise ValueError(f"Attachment {attachment_id} not found")
        mcp_log.info(
            f"[BZ-RES] Attachment {attachment_id} "
            f"file_name={attachment.get('file_name')!r} size={attachment.get('size')}"
        )
        return attachment
