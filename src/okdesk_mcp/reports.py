"""Shared, tested report logic for the Okdesk critical/unanswered reports.

This is the single source of truth for the exact filtering algorithm used by
both `scripts/debug_report.py` and the `okdesk-mcp-report` CLI. Consumers that
need the *authoritative* dataset (e.g. a corporate skill) should run the CLI
instead of re-deriving this logic from individual MCP tool calls — that is
what guarantees the two surfaces return the same result set.

Contains no business-specific values (no hardcoded category, tenant, or
thresholds); callers supply those as parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .client import OkdeskClient

_OKDESK_TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M"


def format_cutoff(now: datetime, hours: int) -> str:
    from datetime import timedelta

    return (now - timedelta(hours=hours)).strftime(_OKDESK_TIMESTAMP_FORMAT)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def is_strict_unanswered(
    issue: dict[str, Any], comments: list[dict[str, Any]], cutoff: datetime
) -> bool:
    """True when the latest item on the issue was authored by a client and
    is older than `cutoff`. Falls back to issue creation when there are no
    comments yet."""
    if comments:
        latest = max(comments, key=lambda comment: comment["published_at"])
        author = latest.get("author") or {}
        timestamp = latest.get("published_at")
    else:
        author = issue.get("author") or {}
        timestamp = issue.get("created_at")

    return (
        author.get("type") == "contact"
        and isinstance(timestamp, str)
        and parse_timestamp(timestamp) < cutoff
    )


@dataclass
class PagedResult:
    issues: list[dict[str, Any]] = field(default_factory=list)
    pages_fetched: int = 0
    truncated: bool = False


def fetch_critical_tickets(
    client: OkdeskClient,
    *,
    now: datetime,
    hours: int,
    company_category_ids: list[str] | None,
    priority_codes: list[str] | None = None,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """Return page 1 of critical tickets created within `hours`. Callers who
    need more than one page should raise page_size (max 50) rather than loop
    — critical-ticket volume is expected to stay small."""
    return client.list_issues(
        priority_codes=priority_codes or ["Critical"],
        company_category_ids=company_category_ids,
        created_since=format_cutoff(now, hours),
        page_size=page_size,
    )


def resolve_active_status_codes(client: OkdeskClient) -> list[str]:
    statuses = client.list_issue_statuses()
    return [s["code"] for s in statuses if not s.get("final", False)]


def fetch_strict_unanswered_tickets(
    client: OkdeskClient,
    *,
    now: datetime,
    hours: int,
    company_category_ids: list[str] | None,
    active_status_codes: list[str] | None = None,
    page_size: int = 50,
    max_pages: int = 10,
) -> PagedResult:
    """Fetch every `without_answer` candidate across up to `max_pages` pages,
    then apply the strict last-item-author/age check per issue. This is the
    one place that check happens — the debug script and the CLI both call
    into this function so they can never diverge."""
    from datetime import timedelta

    if active_status_codes is None:
        active_status_codes = resolve_active_status_codes(client)

    cutoff = now - timedelta(hours=hours)

    result = PagedResult()
    page = 1
    while page <= max_pages:
        candidates = client.list_issues(
            status_codes=active_status_codes,
            company_category_ids=company_category_ids,
            without_answer=True,
            page=page,
            page_size=page_size,
        )
        result.pages_fetched = page
        for issue in candidates:
            issue_id = issue.get("id")
            if not isinstance(issue_id, int):
                continue
            comments = client.list_issue_comments(issue_id)
            if is_strict_unanswered(issue, comments, cutoff):
                result.issues.append(issue)
        if len(candidates) < page_size:
            break
        page += 1
    else:
        # Loop exhausted max_pages without a short page: more may exist.
        result.truncated = True

    return result
