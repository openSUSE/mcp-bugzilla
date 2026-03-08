"""
This is an MCP server for bugzilla which provides a few helpful
functions to assist the LLMs with required context

Author: Sai Karthik <kskarthik@disroot.org>
License: Apache 2.0
"""

import importlib.metadata
from typing import Any, List

from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from fastmcp.dependencies import CurrentHeaders, Depends
from fastmcp.exceptions import PromptError, ResourceError, ToolError, ValidationError
from typing import Optional

from .mcp_utils import Bugzilla, mcp_log

# The FastMCP instance
mcp = FastMCP("Bugzilla")

# Global dict to hold command-line arguments, populated by main() in __init__.py
cli_args: dict[str, Any] = {}

# Global variable to hold the base_url, set by the start() function
base_url: str = ""


@asynccontextmanager
async def get_bz(headers: dict = CurrentHeaders()) -> Bugzilla:
    """Dependency to get the current Bugzilla client"""
    mcp_log.debug("api_key: Checking")

    api_key_header = cli_args.get("api_key_header", "ApiKey")
    api_key_value = headers.get(api_key_header.lower())

    if not api_key_value:
        raise ValidationError(f"`{api_key_header}` header is required")

    mcp_log.debug("api_key: Found")
    bz = Bugzilla(
        url=base_url,
        api_key=api_key_value,
        use_auth_header=cli_args.get("use_auth_header", False)
    )
    try:
        yield bz
    finally:
        await bz.close()




@mcp.tool()
async def bug_info(id: int, bz: Bugzilla = Depends(get_bz)) -> dict[str, Any]:
    """Returns the entire information about a given bugzilla bug id"""

    mcp_log.info(f"[LLM-REQ] bug_info(id={id})")

    try:
        result = await bz.bug_info(id)
        return result

    except Exception as e:
        raise ToolError(f"Failed to fetch bug info\nReason: {e}")


@mcp.tool()
async def bug_comments(
    id: int, include_private_comments: bool = False, bz: Bugzilla = Depends(get_bz)
) -> List[dict[str, Any]]:
    """Returns the comments of given bug id
    Private comments are not included by default
    but can be explicitly requested
    """

    mcp_log.info(
        f"[LLM-REQ] bug_comments(id={id}, include_private_comments={include_private_comments})"
    )

    try:
        all_comments = await bz.bug_comments(id)

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


@mcp.tool()
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


@mcp.tool()
async def bugs_quicksearch(
    query: str,
    status: Optional[str] = "ALL",
    include_fields: Optional[
        str
    ] = "id,product,component,assigned_to,status,resolution,summary,last_change_time",
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    bz: Bugzilla = Depends(get_bz),
) -> List[Any]:
    """Search bugs using bugzilla's quicksearch syntax
    
    To reduce the token limit & response time, only returns a subset of fields for each bug
    The user can query full details of each bug using the bug_info tool
    """

    mcp_log.info(
        f"[LLM-REQ] bugs_quicksearch(query='{query}',status='{status}', include_fields='{include_fields}', limit={limit}, offset={offset})"
    )

    try:
        # We moved quicksearch logic to mcp_utils
        bugs = await bz.quicksearch(query, status, include_fields, limit, offset)

        mcp_log.info(f"[LLM-RES] Found {len(bugs)} bugs")
        return bugs

    except Exception as e:
        raise ToolError(f"Search failed: {e}")


@mcp.tool()
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


@mcp.tool()
def server_url_resource() -> str:
    """bugzilla server's base url"""
    mcp_log.info("[LLM-REQ] server_url_resource()")
    return base_url


@mcp.tool()
def bug_url(bug_id: int) -> str:
    """returns the bug url"""
    mcp_log.info(f"[LLM-REQ] bug_url(bug_id={bug_id})")
    return f"{base_url}/show_bug.cgi?id={bug_id}"


@mcp.tool()
def mcp_server_info_resource() -> dict[str, Any]:
    """Returns the args being used by the current server instance"""
    mcp_log.info("[LLM-REQ] mcp_server_info_resource()")
    info = cli_args.copy()
    info["version"] = importlib.metadata.version("mcp-bugzilla")
    return info


@mcp.tool()
def get_current_headers_resource(headers: dict = CurrentHeaders()) -> dict[str, Any]:
    """Returns the headers being provided by the current http request"""
    mcp_log.info("[LLM-REQ] get_current_headers_resource()")
    return headers


@mcp.tool()
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


@mcp.tool()
async def update_bug_status(
    bug_id: int,
    status: str,
    resolution: Optional[str] = None,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz)
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

    # Validate: CLOSED requires resolution
    if status == "CLOSED" and not resolution:
        raise ToolError("Resolution is required when setting status to CLOSED (e.g., FIXED, WONTFIX, NOTABUG, DUPLICATE)")

    try:
        result = await bz.update_bug(bug_id, updates, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to update bug status\n{e}")


@mcp.tool()
async def assign_bug(
    bug_id: int,
    assignee: str,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz)
) -> dict[str, Any]:
    """Assign a bug to a user. Optionally add a comment.

    Args:
        bug_id: Bug ID to assign
        assignee: Email address of the assignee
        comment: Optional comment explaining the assignment
    """
    mcp_log.info(
        f"[LLM-REQ] assign_bug(bug_id={bug_id}, assignee='{assignee}')"
    )
    try:
        result = await bz.update_bug(bug_id, {"assigned_to": assignee}, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to assign bug\n{e}")


@mcp.tool()
async def update_bug_fields(
    bug_id: int,
    priority: Optional[str] = None,
    severity: Optional[str] = None,
    resolution: Optional[str] = None,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz)
) -> dict[str, Any]:
    """Update various bug fields. All fields are optional.

    Args:
        bug_id: Bug ID to update
        priority: Priority (e.g., urgent, high, medium, low, unspecified)
        severity: Severity (e.g., urgent, high, medium, low, unspecified)
        resolution: Resolution (e.g., FIXED, WONTFIX, NOTABUG, DUPLICATE) - only for closed bugs
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

    if not updates:
        raise ToolError("At least one field must be specified")

    try:
        result = await bz.update_bug(bug_id, updates, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to update bug fields\n{e}")


@mcp.tool()
async def add_cc_to_bug(
    bug_id: int,
    cc_email: str,
    bz: Bugzilla = Depends(get_bz)
) -> dict[str, Any]:
    """Add an email address to the CC list of a bug.

    Args:
        bug_id: Bug ID
        cc_email: Email address to add to CC list
    """
    mcp_log.info(
        f"[LLM-REQ] add_cc_to_bug(bug_id={bug_id}, cc_email='{cc_email}')"
    )
    try:
        result = await bz.update_bug(bug_id, {"cc": {"add": [cc_email]}}, "")
        return result
    except Exception as e:
        raise ToolError(f"Failed to add CC\n{e}")


@mcp.tool()
async def mark_as_duplicate(
    bug_id: int,
    duplicate_of: int,
    comment: str = "",
    bz: Bugzilla = Depends(get_bz)
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

    updates = {
        "status": "CLOSED",
        "resolution": "DUPLICATE",
        "dupe_of": duplicate_of
    }

    try:
        result = await bz.update_bug(bug_id, updates, comment)
        return result
    except Exception as e:
        raise ToolError(f"Failed to mark as duplicate\n{e}")


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


def start():
    """
    Starts the FastMCP server for Bugzilla.
    """
    global base_url
    base_url = cli_args["bugzilla_server"]
    # Ensure base_url doesn't have trailing slash for consistency
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    # Seletively disable components before running the server
    disable_components_selectively()

    mcp_log.info(f"Starting Bugzilla MCP server on {cli_args['host']}:{cli_args['port']}")

    mcp.run(transport="http", host=cli_args["host"], port=cli_args["port"])
