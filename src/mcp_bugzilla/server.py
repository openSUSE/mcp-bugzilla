"""
This is an MCP server for bugzilla which provides a few helpful
functions to assist the LLMs with required context

Author: Sai Karthik <kskarthik@disroot.org>
License: Apache 2.0
"""

import importlib.metadata
from typing import Any, List

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import PromptError, ToolError, ValidationError
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext

from .mcp_utils import Bugzilla, bugzilla_client, mcp_log

# The FastMCP instance
mcp = FastMCP("Bugzilla")

# Global dict to hold command-line arguments, populated by main() in __init__.py
cli_args: dict[str, Any] = {}

# Global variable to hold the base_url, set by the start() function
base_url: str = ""

# check for the required headers which contain the api_key header
# required by all the tools & prompts to make the api calls
class ValidateHeaders(Middleware):
    """Validate incoming HTTP headers"""

    async def on_message(self, context: MiddlewareContext, call_next):
        mcp_log.debug("api_key: Checking")

        api_key_header = cli_args.get("api_key_header", "ApiKey")
        headers = get_http_headers()
        api_key_value = headers.get(api_key_header.lower())

        if api_key_value:
            # Create a new Bugzilla client for this request context
            bz = Bugzilla(url=base_url, api_key=api_key_value)
            token = bugzilla_client.set(bz)
            mcp_log.debug("api_key: Found")

            try:
                return await call_next(context)
            finally:
                # Cleanup: close the client and reset the context var
                await bz.close()
                bugzilla_client.reset(token)
        else:
            raise ValidationError(f"`{api_key_header}` header is required")


mcp.add_middleware(ValidateHeaders())


def get_bz() -> Bugzilla:
    """Helper to get the current Bugzilla client from context"""
    bz = bugzilla_client.get()
    if not bz:
        raise ToolError("Bugzilla client not initialized in context")
    return bz


@mcp.tool()
async def bug_info(id: int) -> dict[str, Any]:
    """Returns the entire information about a given bugzilla bug id"""

    mcp_log.info(f"[LLM-REQ] bug_info(id={id})")

    try:
        bz = get_bz()
        result = await bz.bug_info(id)
        return result

    except Exception as e:
        raise ToolError(f"Failed to fetch bug info\nReason: {e}")


@mcp.tool()
async def bug_comments(id: int, include_private_comments: bool = False) -> List[dict[str, Any]]:
    """Returns the comments of given bug id
    Private comments are not included by default
    but can be explicitely requested
    """

    mcp_log.info(
        f"[LLM-REQ] bug_comments(id={id}, include_private_comments={include_private_comments})"
    )

    try:
        bz = get_bz()
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
async def add_comment(bug_id: int, comment: str, is_private: bool = False) -> dict[str, int]:
    """Add a comment to a bug. It can optionally be private. If success, returns the created comment id."""
    mcp_log.info(
        f"[LLM-REQ] add_comment(bug_id={bug_id}, comment='{comment}', is_private={is_private})"
    )
    try:
        bz = get_bz()
        result = await bz.add_comment(bug_id, comment, is_private)
        return result
    except Exception as e:
        raise ToolError(f"Failed to create a comment\n{e}")


@mcp.tool()
async def bugs_quicksearch(query: str, limit: int = 50, offset: int = 0) -> List[Any]:
    """Search bugs using bugzilla's quicksearch syntax
    
    To reduce the token limit & response time, only returns a subset of fields for each bug
    The user can query full details of each bug using the bug_info tool
    """

    mcp_log.info(
        f"[LLM-REQ] bugs_quicksearch(query='{query}', limit={limit}, offset={offset})"
    )

    try:
        bz = get_bz()
        # We moved quicksearch logic to mcp_utils
        all_bugs = await bz.quicksearch(query, limit, offset)

        bugs_with_essential_fields = []
        for bug in all_bugs:
            bugs_with_essential_fields.append({
                "bug_id": bug.get("id"),
                "product": bug.get("product"),
                "component": bug.get("component"),
                "assigned_to": bug.get("assigned_to"),
                "status": bug.get("status"),
                "resolution": bug.get("resolution"),
                "summary": bug.get("summary"),
                "last_updated": bug.get("last_change_time"),
            })

        mcp_log.info(f"[LLM-RES] Found {len(bugs_with_essential_fields)} bugs")
        return bugs_with_essential_fields

    except Exception as e:
        raise ToolError(f"Search failed: {e}")


@mcp.tool()
async def learn_quicksearch_syntax() -> str:
    """Access the documentation of the bugzilla quicksearch syntax.
    LLM can learn using this tool. Response is in HTML"""

    mcp_log.info("[LLM-REQ] learn_quicksearch_syntax()")

    try:
        bz = get_bz()
        # We can use the client to fetch this page too, though it's not a rest API
        # Using the underlying client for convenience
        url = f"{bz.base_url}/page.cgi?id=quicksearch.html"
        r = await bz.client.get(url)  # Use absolute URL since base_url of client is /rest
        
        # Wait, bz.client.base_url is .../rest.
        # So we should use a new request or adjust.
        # Actually easier to just use a new async request or reuse the client without prefix if possible.
        # httpx client handles absolute URLs by ignoring base_url.
        
        if r.status_code != 200:
            raise PromptError(
                f"Failed to fetch bugzilla quicksearch_syntax with status code {r.status_code}"
            )

        mcp_log.info(f"[LLM-RES] Fetched {len(r.text)} chars of documentation")
        return r.text
    except Exception as e:
        raise PromptError(f"Failed to fetch quicksearch documentation: {e}")


@mcp.tool()
def server_url() -> str:
    """bugzilla server's base url"""
    mcp_log.info("[LLM-REQ] server_url()")
    # server_url is static per instance, doesn't need BZ client really,
    # but base_url global is fine as it's set at startup.
    return base_url


@mcp.tool()
def bug_url(bug_id: int) -> str:
    """returns the bug url"""
    mcp_log.info(f"[LLM-REQ] bug_url(bug_id={bug_id})")
    # This just constructs a URL string, so sync is fine.
    return f"{base_url}/show_bug.cgi?id={bug_id}"


@mcp.tool()
def mcp_server_info() -> dict[str, Any]:
    """Returns the args being used by the current server instance"""
    mcp_log.info("[LLM-REQ] mcp_server_info()")
    info = cli_args.copy()
    info["version"] = importlib.metadata.version("mcp-bugzilla")
    return info


@mcp.tool()
def get_current_headers() -> dict[str, Any]:
    """Returns the headers being provided by the current http request"""
    mcp_log.info("[LLM-REQ] get_current_headers()")
    return get_http_headers()


@mcp.prompt()
async def summarize_bug_comments(id: int) -> str:
    """Summarizes all the comments of a bug"""
    
    mcp_log.info(f"[LLM-REQ] summarize_bug_comments(id={id})")

    try:
        bz = get_bz()
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


def start():
    """
    Starts the FastMCP server for Bugzilla.
    """
    global base_url
    base_url = cli_args["bugzilla_server"]
    # Ensure base_url doesn't have trailing slash for consistency
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    mcp.run(transport="http", host=cli_args["host"], port=cli_args["port"])
