"""Bugzilla Quicksearch syntax reference documentation."""

QUICKSEARCH_SYNTAX_DOC = """# Bugzilla Quicksearch Syntax Reference

Bugzilla Quicksearch provides a concise, search-box syntax for querying bugs.
By default, queries match only **open bugs** (e.g., UNCONFIRMED, NEW, ASSIGNED, REOPENED) and searches are case-insensitive.

## Basic Text Search
- **Words**: Entering words searches across `summary`, `product`, `component`, `keywords`, `whiteboard`, and `comments`.
  - Example: `crash bluetooth` (searches for open bugs matching both words)
- **Substring matching**: Plain text words match partial words (e.g., `cat` matches `catch` or `certificate`).
- **Quotes**: Use double quotes for exact multi-word phrases.
  - Example: `"kernel panic"`
- **Bug Number / Alias**: Entering a bug number (or comma-separated numbers) searches directly by ID.
  - Example: `123456` or `123456,123457`

## Status Shortcuts
- **ALL**: Include both open and closed bugs (default is open bugs only).
  - Example: `ALL product:openSUSE crash`
- **OPEN**: Explicitly search open bugs only.
- **CLOSED**: Search closed/resolved bugs only.
- Specific statuses can also be specified with `status:<STATUS>` (e.g., `status:NEW,ASSIGNED` or `status:RESOLVED`).

## Field Searches (`field:value`)
Search specific fields using `field:value`. Multiple values separated by commas act as a logical **OR**.

| Field Prefix | Description | Example |
| :--- | :--- | :--- |
| `product:` | Filter by product name | `product:openSUSE` or `product:"SUSE Linux Enterprise Server"` |
| `component:` | Filter by component name | `component:Kernel` or `component:"Security Tools"` |
| `status:` | Bug status (`NEW`, `ASSIGNED`, `RESOLVED`, etc.) | `status:RESOLVED,CLOSED` |
| `resolution:` | Resolution reason (`FIXED`, `DUPLICATE`, `WONTFIX`, etc.) | `resolution:FIXED` |
| `assigned_to:` / `assignee:` | Assignee login or email | `assigned_to:maintainer@example.com` |
| `reporter:` | Reporter login or email | `reporter:user@example.com` |
| `cc:` | User in the CC list | `cc:developer@example.com` |
| `priority:` | Priority level | `priority:P1,P2` |
| `severity:` | Severity level | `severity:critical,blocker` |
| `keywords:` | Keywords attached to bug | `keywords:regression` |
| `whiteboard:` | Status whiteboard text | `whiteboard:"needs-triage"` |
| `flag:` | Flags set on the bug | `flag:needinfo?` |

## Operators & Modifiers
- **Multiple terms (AND)**: Separate terms with spaces.
  - Example: `product:openSUSE component:Kernel status:NEW`
- **Comma (OR)**: Separate values within a field with commas.
  - Example: `severity:blocker,critical`
- **Negation (`-`)**: Prefix a term or field filter with `-` to negate it.
  - Example: `-status:RESOLVED` or `-product:Test`
- **OR Operator (`|`)**: Matches either term in summary and status whiteboard.
  - Example: `gnome|kde`

## Common Query Examples
- Search recent or open regressions in a product:
  `product:Firefox keywords:regression`
- Search all bugs reported by a user including closed ones:
  `ALL reporter:alice@example.com`
- Search critical or blocker bugs in a specific component:
  `component:Networking severity:blocker,critical`
- Search open bugs excluding resolved:
  `product:openSUSE -status:RESOLVED`
"""
