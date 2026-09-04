"""FastMCP server exposing read-only Okdesk issue data."""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import OkdeskClient, OkdeskError

mcp = FastMCP("Okdesk")


def _client() -> OkdeskClient:
    domain = os.environ.get("OKDESK_DOMAIN")
    api_token = os.environ.get("OKDESK_API_TOKEN")
    if not domain or not api_token:
        raise OkdeskError("OKDESK_DOMAIN and OKDESK_API_TOKEN must be configured")
    return OkdeskClient(domain, api_token)


@mcp.tool()
def list_issues(
    status_codes: list[str] | None = None,
    priority_codes: list[str] | None = None,
    created_since: str | None = None,
    updated_until: str | None = None,
    without_answer: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """Return ONE page (default 50, max 50) of issues filtered by status, priority,
    creation date, update date, and reply state. Always narrow with filters first;
    only request additional pages (page=2, 3, ...) if the result is exactly page_size
    long, meaning more may exist. Never fetch unfiltered history in a loop."""
    return _client().list_issues(
        status_codes=status_codes,
        priority_codes=priority_codes,
        created_since=created_since,
        updated_until=updated_until,
        without_answer=without_answer,
        page=page,
        page_size=page_size,
    )


@mcp.tool()
def list_issue_priorities() -> list[dict[str, Any]]:
    """Return the Okdesk priority definitions and their codes."""
    return _client().list_issue_priorities()


@mcp.tool()
def list_issue_statuses() -> list[dict[str, Any]]:
    """Return the Okdesk issue statuses and their final-state flags."""
    return _client().list_issue_statuses()


@mcp.tool()
def list_issue_comments(issue_id: int) -> list[dict[str, Any]]:
    """Return the full comment history for an Okdesk issue."""
    return _client().list_issue_comments(issue_id)


@mcp.tool()
def get_issue(issue_id: int) -> dict[str, Any]:
    """Return the full data for an Okdesk issue by its numeric identifier."""
    return _client().get_issue(issue_id)


@mcp.tool()
def issue_url(issue_id: int) -> str:
    """Return the direct service-desk URL for an Okdesk issue."""
    domain = os.environ.get("OKDESK_DOMAIN")
    if not domain:
        raise OkdeskError("OKDESK_DOMAIN must be configured")
    return f"{domain.rstrip('/')}/issues/{issue_id}"


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
