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

#### Bug Search

- **`bugs_quicksearch(query: str, status: str = "ALL", include_fields: str = "...", limit: int = 50, offset: int = 0)`**: Executes a search for bugs using Bugzilla's powerful [quicksearch syntax](https://bugzilla.readthedocs.io/en/latest/using/finding.html#quicksearch).
  - **Parameters**:
    - `query`: A quicksearch query string (e.g., `"product:Firefox"`)
    - `status`: Bug status to filter by (default: `"ALL"`)
    - `include_fields`: Comma-separated list of fields to return (default: `"id,product,component,assigned_to,status,resolution,summary,last_change_time"`)
    - `limit`: Maximum number of results to return (default: `50`)
    - `offset`: Number of results to skip for pagination (default: `0`)
  - **Returns**: A list of dictionaries, each containing essential bug fields:
    - `bug_id`: The bug ID
    - `product`: Product name
    - `component`: Component name
    - `assigned_to`: Assigned user email
    - `status`: Current status
    - `resolution`: Resolution (if resolved)
    - `summary`: Bug summary
    - `last_updated`: Last update timestamp
  - **Note**: Returns a curated subset of fields to optimize token usage. Use `bug_info()` to get full details for specific bugs.
  - **Example**: `bugs_quicksearch("product:Firefox", status="NEW", limit=10)`

#### Utility Tools

- **`bug_url(bug_id: int)`**: Constructs and returns the direct URL to a specific bug on the Bugzilla server.
  - **Returns**: A string representing the bug's URL (e.g., `"https://bugzilla.example.com/show_bug.cgi?id=12345"`)

### Resources

The server exposes several resources for documentation and server information:

- **`doc://quicksearch`**: Provides access to the official Bugzilla quicksearch syntax documentation.
  - **Use case**: Allows LLMs to learn and formulate effective search queries dynamically.

- **`info://server-url`**: Returns the base URL of the configured Bugzilla server.
  - **Returns**: A string representing the base URL (e.g., `"https://bugzilla.example.com"`)

- **`info://mcp-server`**: Returns the configuration arguments being used by the current server instance.
  - **Returns**: A dictionary containing server configuration including version, host, port, and API key header name.

- **`info://current-headers`**: Returns the HTTP headers from the current request.
  - **Returns**: A dictionary of HTTP headers (useful for debugging authentication).

### Prompts

The server provides the following prompt templates:

- **`summarize_bug_comments(id: int)`**: Generates a detailed summary prompt for all comments of a given bug ID.
  - **Returns**: A well-structured prompt that, when used with an LLM, produces a formatted summary of the bug's comments
  - **Format**: Includes usernames (bold italic), dates (bold), and human-readable timestamps
  - **Example**: `summarize_bug_comments(12345)` returns a prompt that can be used to generate a comment summary

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

**Note**: Command-line arguments take precedence over environment variables.

### Environment Variables

You can configure the server using environment variables instead of command-line arguments:

```bash
export BUGZILLA_SERVER=https://bugzilla.example.com
export MCP_HOST=127.0.0.1
export MCP_PORT=8000
export MCP_API_KEY_HEADER=ApiKey
export LOG_LEVEL=INFO  # Optional: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Selective Disabling (Optional)
export MCP_BUGZILLA_DISABLED_METHODS=bug_info,bug_comments

mcp-bugzilla
```

### Component Disabling

The server allows you to selectively disable specific tools or prompts using an environment variable. This is useful for restricting functionality based on security or resource requirements.

**Method**: `MCP_BUGZILLA_DISABLED_METHODS=component1,component2`

| Component | Name in `MCP_BUGZILLA_DISABLED_METHODS` |
|-----------|------------------------------------------|
| `bug_info` (tool) | `BUG_INFO` |
| `bug_comments` (tool) | `BUG_COMMENTS` |
| `add_comment` (tool) | `ADD_COMMENT` |
| `bugs_quicksearch` (tool) | `BUGS_QUICKSEARCH` |
| `bug_url` (tool) | `BUG_URL` |
| `summarize_bug_comments` (prompt) | `SUMMARIZE_BUG_COMMENTS` |

**Note**: Resources (like `info://server-url`) cannot be disabled via this mechanism.

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
     -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "server_url"}, "id": 1}'
   ```

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
