# Bugzilla Model Context Protocol (MCP) Server

[![Tests](https://github.com/openSUSE/mcp-bugzilla/actions/workflows/tests.yml/badge.svg)](https://github.com/openSUSE/mcp-bugzilla/actions/workflows/tests.yml)

A robust MCP server that provides seamless interaction with Bugzilla instances through the Model Context Protocol. This server exposes a comprehensive set of tools and prompts, enabling AI models and other MCP clients to efficiently query bug information, manage comments, and leverage Bugzilla's powerful quicksearch capabilities.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

### Tools

The server provides the following tools for interacting with Bugzilla:

#### Bug Information

- **`bug_info(id: int)`**: Retrieves comprehensive details for a specified Bugzilla bug ID.
  - **Returns**: A dictionary containing all available information about the bug (status, assignee, summary, description, attachments, etc.)
  - **Example**: `bug_info(12345)` returns complete bug details

- **`bug_comments(id: int, include_private_comments: bool = False)`**: Fetches all comments associated with a given bug ID.
  - **Parameters**:
    - `id`: The bug ID to fetch comments for
    - `include_private_comments`: Whether to include private comments (default: `False`)
  - **Returns**: A list of comment dictionaries, each containing author, timestamp, text, and privacy status
  - **Example**: `bug_comments(12345, include_private_comments=True)` returns all comments including private ones

- **`add_comment(bug_id: int, comment: str, is_private: bool = False)`**: Adds a new comment to a specified bug.
  - **Parameters**:
    - `bug_id`: The bug ID to add a comment to
    - `comment`: The comment text to add
    - `is_private`: Whether the comment should be private (default: `False`)
  - **Returns**: A dictionary containing the ID of the newly created comment
  - **Example**: `add_comment(12345, "Fixed in version 2.0", is_private=False)`

#### Write Operations

**Note**: Write operations require appropriate Bugzilla permissions. These tools enable bug management and workflow automation.

* **`update_bug_status(bug_id: int, status: str, resolution: str = None, comment: str = "")`**: Updates the status of a bug with optional comment.

  + **Parameters**:
    - `bug_id`: The bug ID to update
    - `status`: New status (e.g., `NEW`, `ASSIGNED`, `MODIFIED`, `ON_QA`, `VERIFIED`, `CLOSED`)
    - `resolution`: Required when status is `CLOSED` (e.g., `FIXED`, `WONTFIX`, `NOTABUG`, `DUPLICATE`)
    - `comment`: Optional comment explaining the status change
  + **Returns**: A dictionary containing the updated bug fields
  + **Example**: `update_bug_status(12345, "CLOSED", resolution="FIXED", comment="Fixed in version 2.0")`

* **`assign_bug(bug_id: int, assignee: str, comment: str = "")`**: Assigns a bug to a user.

  + **Parameters**:
    - `bug_id`: The bug ID to assign
    - `assignee`: Email address of the assignee
    - `comment`: Optional comment explaining the assignment
  + **Returns**: A dictionary containing the updated bug fields
  + **Example**: `assign_bug(12345, "developer@example.com", comment="You're the expert on this component")`

* **`update_bug_fields(bug_id: int, priority: str = None, severity: str = None, resolution: str = None, comment: str = "")`**: Updates various bug fields.

  + **Parameters**:
    - `bug_id`: The bug ID to update
    - `priority`: Priority level (e.g., `urgent`, `high`, `medium`, `low`, `unspecified`)
    - `severity`: Severity level (e.g., `urgent`, `high`, `medium`, `low`, `unspecified`)
    - `resolution`: Resolution (only for closed bugs)
    - `comment`: Optional comment explaining the changes
  + **Returns**: A dictionary containing the updated bug fields
  + **Example**: `update_bug_fields(12345, priority="high", severity="urgent", comment="Escalating due to customer impact")`

* **`add_cc_to_bug(bug_id: int, cc_email: str)`**: Adds an email address to the CC list of a bug.

  + **Parameters**:
    - `bug_id`: The bug ID
    - `cc_email`: Email address to add to CC list
  + **Returns**: A dictionary containing the updated bug fields
  + **Example**: `add_cc_to_bug(12345, "manager@example.com")`

* **`mark_as_duplicate(bug_id: int, duplicate_of: int, comment: str = "")`**: Marks a bug as a duplicate of another bug and closes it.

  + **Parameters**:
    - `bug_id`: The bug ID to mark as duplicate
    - `duplicate_of`: The bug ID this is a duplicate of
    - `comment`: Optional comment (auto-generated if not provided)
  + **Returns**: A dictionary containing the updated bug fields including status `CLOSED`, resolution `DUPLICATE`, and `dupe_of` reference
  + **Example**: `mark_as_duplicate(12345, 789012, comment="Same root cause as the original report")`

#### Bug Search

- **`bugs_quicksearch(query: str, status: str = "ALL", include_fields: str = "...", limit: int = 50, offset: int = 0)`**: Executes a search for bugs using Bugzilla's powerful [quicksearch syntax](https://bugzilla.readthedocs.io/en/latest/using/finding.html#quicksearch).
  - **Parameters**:
    - `query`: A quicksearch query string (e.g., `"product:Firefox"`)
    - `status`: Bug status to filter by (default: `"ALL"`)
    - `include_fields`: Comma-separated list of fields to return (default: `"id,product,component,assigned_to,status,resolution,summary,last_change_time"`)
    - `limit`: Maximum number of results to return (default: `50`)
    - `offset`: Number of results to skip for pagination (default: `0`)
  - **Returns**: A list of dictionaries, each containing essential bug fields
  - **Example**: `bugs_quicksearch("product:Firefox", status="NEW", limit=10)`

- **`quicksearch_syntax_resource()`**: Returns documentation on Bugzilla's quicksearch syntax.
  - **Returns**: A string containing HTML documentation.

- **`summarize_bug_prompt(id: int)`**: Returns a detailed summary prompt for all comments of a given bug ID.
  - **Returns**: A well-structured summary of the bug's comments including usernames (bold italic) and dates (bold).

#### Utility Tools

- **`bug_url(bug_id: int)`**: Constructs and returns the direct URL to a specific bug on the Bugzilla server.
  - **Returns**: A string representing the bug's URL (e.g., `"https://bugzilla.example.com/show_bug.cgi?id=12345"`)

- **`server_url_resource()`**: Returns the base URL of the configured Bugzilla server.
  - **Returns**: A string representing the base URL.

- **`mcp_server_info_resource()`**: Returns the configuration arguments being used by the current server instance (version, host, port, etc.).
  - **Returns**: A dictionary containing server configuration.

- **`get_current_headers_resource()`**: Returns the HTTP headers from the current request.
  - **Returns**: A dictionary of HTTP headers.


## Requirements

- Python 3.13
- A Bugzilla instance with REST API access
- A Bugzilla user account with an API key
- Network access to the Bugzilla server

## Installation

### Docker / Podman

The easiest way to run the server is using Docker or Podman:

```bash
docker pull kskarthik/mcp-bugzilla
docker run -p 8000:8000 \
  -e BUGZILLA_SERVER=https://bugzilla.example.com \
  kskarthik/mcp-bugzilla \
  --bugzilla-server https://bugzilla.example.com \
  --host 0.0.0.0 \
  --port 8000
```

**Official Docker Hub repository**: https://hub.docker.com/r/kskarthik/mcp-bugzilla/

### From Source

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd mcp-bugzilla
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Run the server:**
   ```bash
   uv run mcp-bugzilla --bugzilla-server https://bugzilla.example.com --host 127.0.0.1 --port 8000
   ```

   This will start the HTTP server at `http://127.0.0.1:8000/mcp/`.

## Configuration

### Command-Line Arguments

The `mcp-bugzilla` command supports the following options:

| Argument | Environment Variable | Default | Description |
|----------|---------------------|---------|-------------|
| `--bugzilla-server <URL>` | `BUGZILLA_SERVER` | *Required* | Base URL of the Bugzilla server (e.g., `https://bugzilla.example.com`) |
| `--host <ADDRESS>` | `MCP_HOST` | `127.0.0.1` | Host address for the MCP server to listen on |
| `--port <PORT>` | `MCP_PORT` | `8000` | Port for the MCP server to listen on |
| `--api-key-header <HEADER_NAME>` | `MCP_API_KEY_HEADER` | `ApiKey` | HTTP header name for the Bugzilla API key |
| `--use-auth-header` | `USE_AUTH_HEADER` | `False` | Use `Authorization: Bearer` header instead of `api_key` query parameter |

**Note**: Command-line arguments take precedence over environment variables.

### Environment Variables

You can configure the server using environment variables instead of command-line arguments:

```bash
export BUGZILLA_SERVER=https://bugzilla.example.com
export MCP_HOST=127.0.0.1
export MCP_PORT=8000
export MCP_API_KEY_HEADER=ApiKey
export LOG_LEVEL=INFO  # Optional: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Selective Disabling Tools (Optional)
export MCP_BUGZILLA_DISABLED_METHODS='bug_info,bug_comments'

mcp-bugzilla
```

### Methods Disabling

The server allows you to selectively disable specific tools or prompts using an environment variable. This is useful for restricting functionality based on security or resource requirements.

**Method**: `MCP_BUGZILLA_DISABLED_METHODS=tool1,tool2`


## Usage

### Starting the Server

Start the server with your Bugzilla instance URL:

```bash
mcp-bugzilla --bugzilla-server https://bugzilla.opensuse.org
```

The server will start listening on `http://127.0.0.1:8000/mcp/` by default.

### Endpoint

The MCP server exposes an HTTP endpoint at:

```
http://<host>:<port>/mcp/
```

For example, with default settings:
```
http://127.0.0.1:8000/mcp/
```

### Authentication

**Required**: All requests must include a Bugzilla API key in the HTTP headers.

1. **Generate an API Key**:
   - Log in to your Bugzilla instance
   - Navigate to your user preferences
   - Go to the "API Keys" section
   - Generate a new API key
   - Copy the API key

2. **Send the API Key**:
   Include the API key in the HTTP request header. By default, the header name is `ApiKey`:

   ```http
   POST /mcp/ HTTP/1.1
   Host: 127.0.0.1:8000
   ApiKey: YOUR_API_KEY_HERE
   Content-Type: application/json
   ```

   You can customize the header name using the `--api-key-header` argument or `MCP_API_KEY_HEADER` environment variable.

3. **Example with curl**:
   ```bash
   curl -X POST http://127.0.0.1:8000/mcp/ \
     -H "ApiKey: YOUR_API_KEY_HERE" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "server_url_resource"}, "id": 1}'
   ```

### Authentication Methods

This server supports two authentication methods for communicating with Bugzilla:

#### Method 1: Query Parameter (Default)

By default, the server sends the API key as a query parameter in the URL:
```bash
mcp-bugzilla --bugzilla-server https://bugzilla.example.com
```

This works with standard Bugzilla instances (Mozilla Bugzilla, openSUSE Bugzilla, etc.).

#### Method 2: Authorization Header (for enterprise instances)

Some Bugzilla instances (such as Red Hat Bugzilla) require the API key to be sent via the `Authorization: Bearer` header instead of as a query parameter. Use the `--use-auth-header` flag for these instances:
```bash
mcp-bugzilla --bugzilla-server https://bugzilla.redhat.com --use-auth-header
```

**When to use `--use-auth-header`:**
- Red Hat Bugzilla (bugzilla.redhat.com)
- Other enterprise Bugzilla instances that reject `api_key` query parameters
- Bugzilla instances with strict authentication requirements

**How it works:**
- **With `--use-auth-header`**: Sends `Authorization: Bearer YOUR_API_KEY` header to Bugzilla
- **Without `--use-auth-header`** (default): Sends `?api_key=YOUR_API_KEY` query parameter to Bugzilla

**Note**: The `--api-key-header` option controls which header name the *MCP server* expects from *clients*, while `--use-auth-header` controls how the *MCP server* authenticates with *Bugzilla*. These are independent settings.

### MCP Client Integration

The server follows the [Model Context Protocol (MCP) specification](https://modelcontextprotocol.io/). It can be integrated with any MCP-compatible client.

**Example MCP client configuration** (format may vary by client):

```json
{
  "mcpServers": {
    "bugzilla": {
      "url": "http://127.0.0.1:8000/mcp/",
      "headers": {
        "ApiKey": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

## API Reference

### Tool Response Format

All tools return JSON responses following the MCP protocol. Successful responses include the tool's return value, while errors include detailed error messages.

### Error Handling

The server provides detailed error messages for common issues:

- **Missing API Key**: Returns `ValidationError` if the required API key header is missing
- **Invalid Bug ID**: Returns `ToolError` with details if a bug ID doesn't exist
- **API Errors**: Returns `ToolError` with the HTTP status code and error message from Bugzilla
- **Network Errors**: Returns `ToolError` for connection or timeout issues

### Logging

The server includes structured logging with color-coded output:

- **LLM Requests/Responses**: Cyan - Shows tool calls from MCP clients
- **Bugzilla API Requests/Responses**: Green - Shows HTTP requests to Bugzilla
- **Errors**: Red - Shows error messages

Set the log level using the `LOG_LEVEL` environment variable:
- `DEBUG`: Detailed debugging information
- `INFO`: General informational messages (default)
- `WARNING`: Warning messages
- `ERROR`: Error messages only
- `CRITICAL`: Critical errors only

## Examples

### Example 1: Get Bug Information

```python
# MCP client call
result = client.call_tool("bug_info", {"id": 12345})
print(result)
# Returns complete bug details including status, assignee, summary, etc.
```

### Example 2: Search for Bugs

```python
# Search for new bugs in Firefox product
result = client.call_tool("bugs_quicksearch", {
    "query": "product:Firefox status:NEW",
    "limit": 10
})
# Returns list of bugs with essential fields
```

### Example 3: Add a Comment

```python
# Add a public comment to a bug
result = client.call_tool("add_comment", {
    "bug_id": 12345,
    "comment": "This issue has been resolved in version 2.0",
    "is_private": False
})
# Returns: {"id": 67890} - the new comment ID
```

### Example 4: Get Bug Comments

```python
# Get all public comments
public_comments = client.call_tool("bug_comments", {
    "id": 12345,
    "include_private_comments": False
})

# Get all comments including private ones
all_comments = client.call_tool("bug_comments", {
    "id": 12345,
    "include_private_comments": True
})
```

### Example 5: Quicksearch Syntax Examples

```python
# Search by product and status
bugs_quicksearch("product:Firefox status:NEW")

# Search by assignee
bugs_quicksearch("assigned_to:user@example.com")

# Search by component
bugs_quicksearch("component:Core status:RESOLVED")

# Search with multiple criteria
bugs_quicksearch("product:Firefox component:JavaScript status:NEW priority:P1")

# Use pagination
page1 = bugs_quicksearch("status:NEW", limit=50, offset=0)
page2 = bugs_quicksearch("status:NEW", limit=50, offset=50)
```

### Example 6: Using with Red Hat Bugzilla

Red Hat Bugzilla requires Authorization header authentication:
```bash
# Start the server with --use-auth-header flag
mcp-bugzilla \
  --bugzilla-server https://bugzilla.redhat.com \
  --use-auth-header \
  --host 127.0.0.1 \
  --port 8000

# Client connects normally - the flag only affects server-to-Bugzilla communication
curl -X POST http://127.0.0.1:8000/mcp/ \
  -H "ApiKey: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "server_url"}, "id": 1}'
```

### Example 7: Update Bug Status
```python
# Close a bug as fixed
result = client.call_tool("update_bug_status", {
    "bug_id": 12345,
    "status": "CLOSED",
    "resolution": "FIXED",
    "comment": "Fixed in commit abc123"
})
```

### Example 8: Assign a Bug
```python
# Assign bug to a developer
result = client.call_tool("assign_bug", {
    "bug_id": 12345,
    "assignee": "developer@example.com",
    "comment": "Please review this regression"
})
```

### Example 9: Mark as Duplicate
```python
# Mark bug as duplicate and close it
result = client.call_tool("mark_as_duplicate", {
    "bug_id": 12345,
    "duplicate_of": 67890,
    "comment": "This is a duplicate of the original report"
})
# Bug is automatically closed with resolution DUPLICATE
```

## Troubleshooting

### Server Won't Start

**Issue**: Server fails to start with "bugzilla-server argument required"

**Solution**: Ensure you provide the `--bugzilla-server` argument or set the `BUGZILLA_SERVER` environment variable:
```bash
mcp-bugzilla --bugzilla-server https://bugzilla.example.com
```

### Authentication Errors

**Issue**: Receiving `ValidationError: ApiKey header is required`

**Solution**: 
1. Ensure you're sending the API key in the correct HTTP header (default: `ApiKey`)
2. Verify the API key is valid and not expired
3. Check that the header name matches your server configuration

### API Errors

**Issue**: Receiving `ToolError` with HTTP status codes

**Common causes**:
- **401 Unauthorized**: Invalid or expired API key
- **404 Not Found**: Bug ID doesn't exist or you don't have permission to view it
- **403 Forbidden**: Insufficient permissions for the requested operation
- **500 Internal Server Error**: Bugzilla server error

**Solution**: Check the error message for details and verify your API key permissions.

### Connection Issues

**Issue**: Cannot connect to Bugzilla server

**Solution**:
1. Verify the Bugzilla server URL is correct and accessible
2. Check network connectivity
3. Ensure the Bugzilla instance has REST API enabled
4. Verify firewall rules allow outbound connections

### Logging Issues

**Issue**: Not seeing enough (or too much) log output

**Solution**: Adjust the `LOG_LEVEL` environment variable:
```bash
export LOG_LEVEL=DEBUG  # For more verbose output
export LOG_LEVEL=ERROR  # For minimal output
```

## License

This project is licensed under the Apache 2.0 License. See the [LICENSE](https://www.apache.org/licenses/LICENSE-2.0.txt) file for details.

**Author**: Sai Karthik <kskarthik@disroot.org>

**Contributors**: https://github.com/openSUSE/mcp-bugzilla/graphs/contributors
