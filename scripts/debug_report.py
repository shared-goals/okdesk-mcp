#!/usr/bin/env python3
"""Manual, direct sanity check for the two Okdesk reports — bypasses MCP/Hermes.

Talks straight to okdesk_mcp.client.OkdeskClient so you can verify the API
contract and filter behavior without going through the agent, the skill, or
a live MCP stdio session. Prints counts first, never dumps full ticket bodies.

Usage:
    OKDESK_DOMAIN=... OKDESK_API_TOKEN=... uv run python scripts/debug_report.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime, timedelta

sys.path.insert(
    0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src")
)

from okdesk_mcp.client import OkdeskClient

_OKDESK_TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M"
_DEFAULT_CRITICAL_HOURS = 24
_DEFAULT_UNANSWERED_HOURS = 48
_DEFAULT_PAGE_SIZE = 50


def _cutoff(hours: int) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).strftime(
        _OKDESK_TIMESTAMP_FORMAT
    )


def _elapsed(start: float) -> float:
    return time.perf_counter() - start


def _env_int(name: str, default: int, *, maximum: int | None = None) -> int:
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {value!r}") from error
    if parsed < 1 or (maximum is not None and parsed > maximum):
        bound = f"1..{maximum}" if maximum is not None else "at least 1"
        raise ValueError(f"{name} must be {bound}, got {parsed}")
    return parsed


def main() -> None:
    domain = os.environ["OKDESK_DOMAIN"]
    token = os.environ["OKDESK_API_TOKEN"]
    client = OkdeskClient(domain, token)
    critical_hours = _env_int("CRITICAL_HOURS", _DEFAULT_CRITICAL_HOURS)
    unanswered_hours = _env_int("UNANSWERED_HOURS", _DEFAULT_UNANSWERED_HOURS)
    page_size = _env_int("PAGE_SIZE", _DEFAULT_PAGE_SIZE, maximum=50)

    print(
        f"parameters: critical_hours={critical_hours}, "
        f"unanswered_hours={unanswered_hours}, page_size={page_size}"
    )
    print(f"== critical tickets (last {critical_hours}h), page 1 ==")
    started = time.perf_counter()
    critical = client.list_issues(
        priority_codes=["Critical"],
        created_since=_cutoff(critical_hours),
        page_size=page_size,
    )
    print(
        f"count on page 1: {len(critical)} (page_size={page_size}; "
        f"more may exist if this is {page_size})"
    )
    print(f"request time: {_elapsed(started):.3f}s")
    for issue in critical[:5]:
        print(f"  #{issue.get('id')} {issue.get('title')!r}")

    print()
    print("== active statuses ==")
    started = time.perf_counter()
    statuses = client.list_issue_statuses()
    active_codes = [s["code"] for s in statuses if not s.get("final", False)]
    print(
        f"active status codes: {len(active_codes)} of {len(statuses)} total; "
        f"request time: {_elapsed(started):.3f}s"
    )

    print()
    print(
        f"== unanswered candidates (active + without_answer, "
        f"strict age target {unanswered_hours}h), page 1 =="
    )
    started = time.perf_counter()
    candidates = client.list_issues(
        status_codes=active_codes, without_answer=True, page_size=page_size
    )
    print(
        f"count on page 1: {len(candidates)} (page_size={page_size}; "
        f"more may exist if this is {page_size})"
    )
    print(f"request time: {_elapsed(started):.3f}s")
    for issue in candidates[:5]:
        print(f"  #{issue.get('id')} {issue.get('title')!r}")


if __name__ == "__main__":
    main()
