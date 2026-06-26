"""
This is an MCP server for bugzilla which provides a few helpful
functions to assist the LLMs with required context

Author: Sai Karthik <kskarthik@disroot.org>
License: Apache 2.0
"""

import base64
import importlib.metadata
import os
import tempfile
from argparse import Namespace
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, List, Literal, Optional

from fastmcp import FastMCP
from fastmcp.dependencies import CurrentHeaders, Depends
from fastmcp.exceptions import PromptError, ResourceError, ToolError, ValidationError

from .mcp_utils import Bugzilla, is_textual, mcp_log, safe_filename

# The FastMCP instance
mcp = FastMCP("Bugzilla")

# Global dict to hold command-line arguments, populated by main() in __init__.py
cli_args: Namespace

# Global variable to hold the base_url, set by the start() function
base_url: str = ""

# Global variable for read-only mode
read_only: bool = False

# Directory where binary / oversized attachments are written by download_attachment,
# set by the start() function from --download-dir / BUGZILLA_DOWNLOAD_DIR.
download_dir: str = ""

# In "auto" delivery, attachments whose decoded text is at or below this size are
# returned inline; anything larger (or any binary attachment) is written to disk.
MAX_INLINE_BYTES: int = 256 * 1024

# Hard ceiling for delivery="inline": refuse to force anything larger into the
# response (it would flood the conversation); the caller should save it instead.
MAX_FORCED_INLINE_BYTES: int = 1024 * 1024


@asynccontextmanager
async def get_bz(headers: dict = CurrentHeaders()) -> Bugzilla:
    """Dependency to get the current Bugzilla client.

    For http transport, the API key is read per-request from the configured header.
    For stdio transport, there is no HTTP request scope, so the key comes from
    the CLI flag / BUGZILLA_API_KEY env var captured at startup.
    """
    mcp_log.debug("api_key: Checking")

    transport = getattr(cli_args, "transport", "http")

    if transport == "stdio":
        api_key_value = getattr(cli_args, "api_key", None)
        if not api_key_value:
            # Defense in depth; main() already validates this at startup.
            raise ValidationError(
                "stdio transport requires --api-key or BUGZILLA_API_KEY env var"
            )
    else:
        api_key_header = getattr(cli_args, "api_key_header", "ApiKey")
        api_key_value = headers.get(api_key_header.lower())
        if not api_key_value:
            raise ValidationError(f"`{api_key_header}` header is required")

    mcp_log.debug("api_key: Found")
    bz = Bugzilla(
        url=base_url,
        api_key=api_key_value,
        use_auth_header=getattr(cli_args, "use_auth_header", False),
    )
    try:
        yield bz
    finally:
        await bz.close()


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def bug_info(bug_ids: set[int], bz: Bugzilla = Depends(get_bz)) -> dict[str, Any]:
    """Returns the entire information for one or more bugzilla bug ids."""

    mcp_log.info(f"[LLM-REQ] bug_info(ids={bug_ids})")

    try:
        result = await bz.bug_info(bug_ids)
        return result

    except Exception as e:
        raise ToolError(f"Failed to fetch bug info\nReason: {e}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def bug_history(
    id: int,
    new_since: Optional[datetime] = None,
    bz: Bugzilla = Depends(get_bz),
) -> list[dict[str, Any]]:
    """Returns the history of given bug id.
    new_since allows filtering history newer than the given date.
    """

    mcp_log.info(f"[LLM-REQ] bug_history(id={id}, new_since={new_since})")

    try:
        history = await bz.bug_history(id, new_since=new_since)
        mcp_log.info(f"[LLM-RES] Returning {len(history)} history items")
        return history
    except Exception as e:
        raise ToolError(f"Failed to fetch bug history\nReason: {e}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def bug_comments(
    id: int,
    include_private_comments: bool = False,
    new_since: Optional[datetime] = None,
    bz: Bugzilla = Depends(get_bz),
) -> List[dict[str, Any]]:
    """Returns the comments of given bug id
    Private comments are not included by default
    but can be explicitly requested.
    new_since allows filtering comments newer than the given date.
    """

    mcp_log.info(
        f"[LLM-REQ] bug_comments(id={id}, include_private_comments={include_private_comments}, new_since={new_since})"
    )

    try:
        all_comments = await bz.bug_comments(id, new_since=new_since)

        if include_private_comments:
            mcp_log.info(
                f"[LLM-RES] Returning {len(all_comments)} comments (including private)"
            )
            return all_comments

        public_comments = [c for c in all_comments if not c.get("is_private", False)]
        mcp_log.info(f"[LLM-RES] Returning {len(public_comments)} public comments")
        return public_comments

    except Exception as e:
        raise ToolError(f"Failed to fetch bug comments\nReason: {e}")


@mcp.tool(
    annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True},
    tags={"write"},
)
async def add_comment(
    bug_id: int, comment: str, is_private: bool = False, bz: Bugzilla = Depends(get_bz)
) -> dict[str, int]:
    """Add a comment to a bug. It can optionally be private. If success, returns the created comment id."""
    mcp_log.info(
        f"[LLM-REQ] add_comment(bug_id={bug_id}, comment='{comment}', is_private={is_private})"
    )
    try:
        result = await bz.add_comment(bug_id, comment, is_private)
        return result
    except Exception as e:
        raise ToolError(f"Failed to create a comment\n{e}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def bugs_quicksearch(
    query: str,
    status: Optional[str] = "ALL",
    include_fields: Optional[
        str
    ] = "id,product,component,assigned_to,status,resolution,summary,last_change_time",
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    bz: Bugzilla = Depends(get_bz),
) -> dict[str, Any]:
    """Search bugs using bugzilla's quicksearch syntax

    To reduce the token limit & response time, only returns a subset of fields for each bug
    The user can query full details of each bug using the bug_info tool
    Returns the top-level bug data envelope containing the matched bugs.
    """

    mcp_log.info(
        f"[LLM-REQ] bugs_quicksearch(query='{query}',status='{status}', include_fields='{include_fields}', limit={limit}, offset={offset})"
    )

    try:
        # We moved quicksearch logic to mcp_utils
        envelope = await bz.quicksearch(query, status, include_fields, limit, offset)

        mcp_log.info(f"[LLM-RES] Returning quicksearch envelope")
        return envelope

    except Exception as e:
        raise ToolError(f"Search failed: {e}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def quicksearch_syntax_resource(bz: Bugzilla = Depends(get_bz)) -> str:
    """Access the documentation of the bugzilla quicksearch syntax. LLM can learn using this tool. Response is in HTML"""

    mcp_log.info("[LLM-REQ] quicksearch_syntax_resource()")

    try:
        # We can use the client to fetch this page too, though it's not a rest API
        # Using the underlying client for convenience
        url = f"{bz.base_url}/page.cgi"
        r = await bz.client.get(
            url, params={"id": "quicksearch.html"}
        )  # Use absolute URL since base_url of client is /rest

        if r.status_code != 200:
            raise ResourceError(
                f"Failed to fetch bugzilla quicksearch_syntax with status code {r.status_code}"
            )

        mcp_log.info(f"[LLM-RES] Fetched {len(r.text)} chars of documentation")
        return r.text
    except Exception as e:
        raise ResourceError(f"Failed to fetch quicksearch documentation: {e}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def bugzilla_server_info(bz: Bugzilla = Depends(get_bz)) -> dict[str, Any]:
    """Returns comprehensive bugzilla server information (url, version, extensions, timezone, time, parameters)."""
    mcp_log.info("[LLM-REQ] bugzilla_server_info()")
    try:
        return await bz.bugzilla_info()
    except Exception as e:
        raise ToolError(f"Failed to fetch bugzilla server info\nReason: {e}")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False}, tags={"read"})
def bug_url(bug_id: int) -> str:
    """returns the bug url"""
    mcp_log.info(f"[LLM-REQ] bug_url(bug_id={bug_id})")
    return f"{base_url}/show_bug.cgi?id={bug_id}"


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def mcp_server_info_resource(bz: Bugzilla = Depends(get_bz)) -> dict[str, Any]:
    """Returns the args being used by the current server instance"""

    mcp_log.info("[LLM-REQ] mcp_server_info_resource()")

    info = vars(cli_args).copy()

    info["mcp_version"] = importlib.metadata.version("mcp-bugzilla")

    try:
        r = await bz.server_version()
        info["bugzilla_server_version"] = r
    except Exception as e:
        mcp_log.info(f"[LLM-RES]: {e}")

    return info


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
def get_current_headers_resource(headers: dict = CurrentHeaders()) -> dict[str, Any]:
    """Returns the headers being provided by the current http request"""
    mcp_log.info("[LLM-REQ] get_current_headers_resource()")
    return headers


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True}, tags={"read"})
async def summarize_bug_prompt(id: int, bz: Bugzilla = Depends(get_bz)) -> str:
    """Summarizes all the comments of a bug"""

    mcp_log.info(f"[LLM-REQ] summarize_bug_prompt(id={id})")

    try:
        comments = await bz.bug_comments(id)

        summary_prompt = f"""
    You are an expert in summarizing bugzilla comments.
    Rules to follow:
    - Summary must be well structured & eye catching
    - Mention usernames & dates wherever relevant.
    - date field must be in human readable format
    - Usernames must be bold italic (***username***) dates must be bold (**date**)

    Comments Data:
    {comments}
    """.strip()

        mcp_log.info(f"[LLM-RES] Generated prompt of length {len(summary_prompt)}")
        return summary_prompt

    except Exception as e:
        raise PromptError(f"Summarize Comments Failed\nReason: {e}")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    tags={"write"},
)
async def update_bug_status(
    bug_id: int,
    status: str,
    resolution: Optional[str] = None,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz),
) -> dict[str, Any]:
    """Update the status of a bug. Optionally add a comment explaining the status change.

    Valid statuses: NEW, ASSIGNED, MODIFIED, ON_QA, VERIFIED, CLOSED
    For CLOSED, you MUST also provide a resolution (FIXED, WONTFIX, NOTABUG, DUPLICATE, etc.)

    Args:
        bug_id: Bug ID to update
        status: New status
        resolution: Resolution (required when status is CLOSED)
        comment: Optional comment explaining the change
    """
    mcp_log.info(
        f"[LLM-REQ] update_bug_status(bug_id={bug_id}, status='{status}', resolution={resolution}, comment='{comment[:50] if comment else ''}...')"
    )

    updates = {"status": status}
    if resolution:
        updates["resolution"] = resolution
    elif status not in ("CLOSED", "VERIFIED"):
        # Clear resolution when reopening
        updates["resolution"] = ""

    # Validate: CLOSED requires resolution
    if status == "CLOSED" and not resolution:
        raise ToolError(
            "Resolution is required when setting status to CLOSED (e.g., FIXED, WONTFIX, NOTABUG, DUPLICATE)"
        )

    try:
        result = await bz.update_bug(bug_id, updates, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to update bug status\n{e}")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    tags={"write"},
)
async def assign_bug(
    bug_id: int, assignee: str, comment: str = "", bz: Bugzilla = Depends(get_bz)
) -> dict[str, Any]:
    """Assign a bug to a user. Optionally add a comment.

    Args:
        bug_id: Bug ID to assign
        assignee: Email address of the assignee
        comment: Optional comment explaining the assignment
    """
    mcp_log.info(f"[LLM-REQ] assign_bug(bug_id={bug_id}, assignee='{assignee}')")
    try:
        result = await bz.update_bug(bug_id, {"assigned_to": assignee}, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to assign bug\n{e}")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    tags={"write"},
)
async def update_bug_fields(
    bug_id: int,
    priority: Optional[str] = None,
    severity: Optional[str] = None,
    resolution: Optional[str] = None,
    custom_fields: Optional[dict[str, Any]] = None,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz),
) -> dict[str, Any]:
    """Update various bug fields. All fields are optional.

    Args:
        bug_id: Bug ID to update
        priority: Priority (e.g., urgent, high, medium, low, unspecified)
        severity: Severity (e.g., urgent, high, medium, low, unspecified)
        resolution: Resolution (e.g., FIXED, WONTFIX, NOTABUG, DUPLICATE) - only for closed bugs
        custom_fields: Dict of custom fields e.g. {"cf_fixed_in": "1.2.3"}
        comment: Optional comment explaining the changes
    """
    mcp_log.info(
        f"[LLM-REQ] update_bug_fields(bug_id={bug_id}, priority={priority}, severity={severity}, resolution={resolution})"
    )

    updates = {}
    if priority:
        updates["priority"] = priority
    if severity:
        updates["severity"] = severity
    if resolution:
        updates["resolution"] = resolution
    if custom_fields:
        updates.update(custom_fields)

    if not updates:
        raise ToolError("At least one field must be specified")

    try:
        result = await bz.update_bug(bug_id, updates, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to update bug fields\n{e}")


@mcp.tool(
    tags={"write"},
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
async def update_bug_dependencies(
    bug_id: int,
    blocks_add: Optional[list[int]] = None,
    blocks_remove: Optional[list[int]] = None,
    depends_on_add: Optional[list[int]] = None,
    depends_on_remove: Optional[list[int]] = None,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz),
) -> dict[str, Any]:
    """Update bug dependency relationships (blocks/depends_on).

    Args:
        bug_id: Bug ID to update
        blocks_add: List of bug IDs this bug should block
        blocks_remove: List of bug IDs to remove from blocks
        depends_on_add: List of bug IDs this bug should depend on
        depends_on_remove: List of bug IDs to remove from depends_on
        comment: Optional comment explaining the changes
    """
    updates = {}
    if blocks_add or blocks_remove:
        updates["blocks"] = {}
        if blocks_add:
            updates["blocks"]["add"] = blocks_add
        if blocks_remove:
            updates["blocks"]["remove"] = blocks_remove
    if depends_on_add or depends_on_remove:
        updates["depends_on"] = {}
        if depends_on_add:
            updates["depends_on"]["add"] = depends_on_add
        if depends_on_remove:
            updates["depends_on"]["remove"] = depends_on_remove

    if not updates:
        raise ToolError("At least one dependency change must be specified")

    try:
        result = await bz.update_bug(bug_id, updates, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to update bug dependencies\n{e}")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    tags={"write"},
)
async def add_cc_to_bug(
    bug_id: int, cc_email: str, bz: Bugzilla = Depends(get_bz)
) -> dict[str, Any]:
    """Add an email address to the CC list of a bug.

    Args:
        bug_id: Bug ID
        cc_email: Email address to add to CC list
    """
    mcp_log.info(f"[LLM-REQ] add_cc_to_bug(bug_id={bug_id}, cc_email='{cc_email}')")
    try:
        result = await bz.update_bug(bug_id, {"cc": {"add": [cc_email]}}, "")
        return result
    except Exception as e:
        raise ToolError(f"Failed to add CC\n{e}")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    tags={"write"},
)
async def mark_as_duplicate(
    bug_id: int, duplicate_of: int, comment: str = "", bz: Bugzilla = Depends(get_bz)
) -> dict[str, Any]:
    """Mark a bug as a duplicate of another bug and close it.

    Args:
        bug_id: Bug ID to mark as duplicate
        duplicate_of: Bug ID this is a duplicate of
        comment: Optional comment (default: auto-generated)
    """
    mcp_log.info(
        f"[LLM-REQ] mark_as_duplicate(bug_id={bug_id}, duplicate_of={duplicate_of})"
    )

    if not comment:
        comment = f"Marking as duplicate of bug {duplicate_of}"

    updates = {"status": "CLOSED", "resolution": "DUPLICATE", "dupe_of": duplicate_of}

    try:
        result = await bz.update_bug(bug_id, updates, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to mark as duplicate\n{e}")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    tags={"write"},
)
async def create_bug(
    product: str,
    component: str,
    summary: str,
    version: str,
    description: str,
    op_sys: str = "All",
    platform: str = "All",
    priority: Optional[str] = None,
    severity: Optional[str] = None,
    cc: Optional[list[str]] = None,
    custom_fields: Optional[dict[str, Any]] = None,
    bz: Bugzilla = Depends(get_bz),
) -> dict[str, Any]:
    """Create a new bug. Returns the new bug id on success.

    Required fields: product, component, summary, version, description. Some
    Bugzilla instances mandate additional fields; the raw Bugzilla error is
    surfaced when that happens (inspect it and retry with the missing field).

    Args:
        product: Product the bug is filed against
        component: Component within the product
        summary: One-line bug summary
        version: Affected product version (e.g. "unspecified")
        description: Initial bug description (the first comment)
        op_sys: Operating system (default "All")
        platform: Hardware platform (default "All")
        priority: Optional priority (e.g. P1..P5 / high..low, instance-specific)
        severity: Optional severity (e.g. critical, normal, minor)
        cc: Optional list of email addresses to CC
        custom_fields: Optional dict of extra/custom fields, e.g. {"cf_foo": "bar"}
    """
    mcp_log.info(
        f"[LLM-REQ] create_bug(product={product!r}, component={component!r}, "
        f"summary={summary!r}, version={version!r})"
    )

    fields: dict[str, Any] = {
        "product": product,
        "component": component,
        "summary": summary,
        "version": version,
        "description": description,
        "op_sys": op_sys,
        "platform": platform,
    }
    if priority:
        fields["priority"] = priority
    if severity:
        fields["severity"] = severity
    if cc:
        fields["cc"] = cc
    if custom_fields:
        fields.update(custom_fields)

    try:
        return await bz.create_bug(fields)
    except Exception as e:
        raise ToolError(f"Failed to create bug\n{e}")


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    tags={"write"},
)
async def add_attachment(
    bug_id: int,
    file_name: str,
    summary: str,
    data: str,
    content_type: str = "text/plain",
    is_patch: bool = False,
    is_private: bool = False,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz),
) -> dict[str, Any]:
    """Attach a file to a bug. Returns the created attachment id(s).

    Args:
        bug_id: Bug to attach the file to
        file_name: File name shown in Bugzilla
        summary: Short description of the attachment
        data: The attachment content, **base64-encoded** (binary-safe)
        content_type: MIME type (ignored by Bugzilla when is_patch=True)
        is_patch: Mark the attachment as a patch
        is_private: Restrict the attachment to the insider group
        comment: Optional comment to add alongside the attachment
    """
    mcp_log.info(
        f"[LLM-REQ] add_attachment(bug_id={bug_id}, file_name={file_name!r}, "
        f"is_patch={is_patch}, is_private={is_private})"
    )

    payload: dict[str, Any] = {
        "ids": [bug_id],
        "file_name": file_name,
        "summary": summary,
        "data": data,
        "content_type": content_type,
        "is_patch": is_patch,
        "is_private": is_private,
    }
    if comment:
        payload["comment"] = comment

    try:
        return await bz.add_attachment(bug_id, payload)
    except Exception as e:
        raise ToolError(f"Failed to add attachment\n{e}")


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    tags={"read"},
)
async def list_attachments(
    bug_id: int, bz: Bugzilla = Depends(get_bz)
) -> list[dict[str, Any]]:
    """List a bug's attachments (metadata only, without the file contents).

    Use this to discover attachment ids, then pass an id to ``download_attachment``
    to fetch the actual file. The base64 ``data`` field is intentionally omitted
    here to keep responses small.

    Args:
        bug_id: The bug whose attachments to list.

    Returns:
        A list of attachment metadata objects (id, file_name, summary,
        content_type, size, is_private, is_obsolete, is_patch, creation_time, ...).
    """
    mcp_log.info(f"[LLM-REQ] list_attachments(bug_id={bug_id})")
    try:
        return await bz.list_attachments(bug_id)
    except Exception as e:
        raise ToolError(f"Failed to list attachments\nReason: {e}")


@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True},
    tags={"read"},
)
async def download_attachment(
    attachment_id: int,
    output_dir: Optional[str] = None,
    delivery: Literal["auto", "inline", "save"] = "auto",
    bz: Bugzilla = Depends(get_bz),
) -> dict[str, Any]:
    """Download a single attachment by id. Discover ids with ``list_attachments``.

    The ``delivery`` argument controls how the content is returned:

    - ``"auto"`` (default): textual attachments (logs, patches, plain/xml/json, ...)
      up to 256 KiB are returned inline as decoded ``content``; binary attachments,
      or larger text, are written to disk and the absolute ``path`` is returned.
    - ``"inline"``: always return the content in the response — decoded ``content``
      for text, or base64 ``data_base64`` for binary. Refused above 1 MiB.
    - ``"save"``: always write the file to disk and return its ``path``.

    Args:
        attachment_id: The attachment id to download.
        output_dir: Directory to save the file in when it is written to disk.
            Defaults to the server's configured download directory
            (--download-dir / BUGZILLA_DOWNLOAD_DIR).
        delivery: One of "auto", "inline", "save" (see above).

    Returns:
        Text inline: ``{"mode": "text", "content": <decoded text>, ...metadata}``.
        Binary inline: ``{"mode": "base64", "data_base64": <base64>, ...metadata}``.
        Saved to disk: ``{"mode": "saved", "path": <abspath>, ...metadata}``.
    """
    mcp_log.info(
        f"[LLM-REQ] download_attachment(attachment_id={attachment_id}, delivery={delivery!r})"
    )
    try:
        att = await bz.get_attachment(attachment_id)
        b64 = att.get("data") or ""
        raw = base64.b64decode(b64)

        content_type = att.get("content_type", "")
        is_text = bool(is_textual(content_type) or att.get("is_patch"))
        meta = {
            "attachment_id": attachment_id,
            "file_name": att.get("file_name"),
            "content_type": content_type,
            "size": len(raw),
            "is_private": att.get("is_private"),
            "is_obsolete": att.get("is_obsolete"),
        }

        def _save() -> dict[str, Any]:
            target = output_dir or download_dir
            os.makedirs(target, exist_ok=True)
            path = os.path.join(
                target,
                f"{attachment_id}-{safe_filename(att.get('file_name'), attachment_id)}",
            )
            with open(path, "wb") as f:
                f.write(raw)
            abspath = os.path.abspath(path)
            mcp_log.info(f"[LLM-RES] attachment {attachment_id} saved to {abspath}")
            return {"mode": "saved", "path": abspath, **meta}

        def _inline() -> dict[str, Any]:
            if len(raw) > MAX_FORCED_INLINE_BYTES:
                raise ToolError(
                    f"Attachment {attachment_id} is {len(raw)} bytes, too large to "
                    f"return inline (limit {MAX_FORCED_INLINE_BYTES}). "
                    "Use delivery='save' or delivery='auto'."
                )
            if is_text:
                mcp_log.info(
                    f"[LLM-RES] attachment {attachment_id} returned inline as text"
                )
                return {
                    "mode": "text",
                    "content": raw.decode("utf-8", errors="replace"),
                    **meta,
                }
            mcp_log.info(
                f"[LLM-RES] attachment {attachment_id} returned inline as base64"
            )
            return {"mode": "base64", "data_base64": b64, **meta}

        if delivery == "save":
            return _save()
        if delivery == "inline":
            return _inline()
        # auto
        if is_text and len(raw) <= MAX_INLINE_BYTES:
            return _inline()
        return _save()
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to download attachment {attachment_id}\nReason: {e}")


def disable_components_selectively():
    """
    Disables MCP components based on environment variables.
    Convention: MCP_BUGZILLA_DISABLED_METHODS=component1,component2
    """
    import os

    # Comma-separated list in MCP_BUGZILLA_DISABLED_METHODS
    disabled_list = os.getenv("MCP_BUGZILLA_DISABLED_METHODS", "").split(",")
    disabled_list = [d.strip().upper() for d in disabled_list if d.strip()]

    # Iterate over all registered components in the local provider
    for key, component in mcp.local_provider._components.items():
        name = getattr(component, "name", None)
        if not name:
            continue

        name_upper = name.upper()

        if name_upper in disabled_list:
            mcp_log.info(f"Disabling component {key} via MCP_BUGZILLA_DISABLED_METHODS")
            mcp.disable(keys={key})


def disable_write_components():
    """
    Disable all components which alter the state of bug
    Invoked when --read-only flag is set
    """
    if read_only:
        mcp_log.info("Disabling all components which can modify bugs")
        # disable all methods with write tags
        mcp.disable(tags={"write"})


def start():
    """
    Starts the FastMCP server for Bugzilla.
    """
    global base_url, read_only, download_dir
    base_url = cli_args.bugzilla_server
    read_only = getattr(cli_args, "read_only", False)
    download_dir = getattr(cli_args, "download_dir", None) or os.path.join(
        tempfile.gettempdir(), "mcp-bugzilla"
    )
    # Ensure base_url doesn't have trailing slash for consistency
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    # Seletively disable components before running the server
    disable_components_selectively()
    disable_write_components()

    transport = getattr(cli_args, "transport", "http")

    run_kwargs = {"show_banner": False, "transport": transport}

    if transport != "stdio":
        run_kwargs.update({"host": cli_args.host, "port": cli_args.port})
        mcp_log.info(f"Starting Bugzilla MCP server on {cli_args.host}:{cli_args.port}")
    else:
        mcp_log.info("Starting Bugzilla MCP server on stdio")

    mcp.run(**run_kwargs)
