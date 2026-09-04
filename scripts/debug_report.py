#!/usr/bin/env python3
"""Manual, direct sanity check for the two Okdesk reports — bypasses MCP/Hermes.

Talks straight to okdesk_mcp.client.OkdeskClient so you can verify the API
contract and filter behavior without going through the agent, the skill, or
a live MCP stdio session. Prints counts first, never dumps full ticket bodies.

Usage:
    OKDESK_DOMAIN=... OKDESK_API_TOKEN=... uv run python scripts/debug_report.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from rich.console import Console
from rich.table import Table

sys.path.insert(
    0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src")
)

from okdesk_mcp.client import OkdeskClient

_OKDESK_TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M"
_DEFAULT_CRITICAL_HOURS = 24
_DEFAULT_UNANSWERED_HOURS = 48
_DEFAULT_PAGE_SIZE = 50
_DEFAULT_COMPANY_CATEGORY_ID = "13"
_console = Console()


def _cutoff(hours: int) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).strftime(
        _OKDESK_TIMESTAMP_FORMAT
    )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_strict_unanswered(
    issue: dict[str, Any], comments: list[dict[str, Any]], cutoff: datetime
) -> bool:
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
        and _parse_timestamp(timestamp) < cutoff
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


def _schema(value: Any, prefix: str = "") -> dict[str, set[str]]:
    paths: dict[str, set[str]] = defaultdict(set)
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths[path].add(type(child).__name__)
            for child_path, types in _schema(child, path).items():
                paths[child_path].update(types)
    elif isinstance(value, list):
        path = f"{prefix}[]"
        paths[path].add("list")
        for child in value:
            for child_path, types in _schema(child, path).items():
                paths[child_path].update(types)
    return dict(paths)


def _print_schema(label: str, entries: list[dict[str, Any]]) -> None:
    fields: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        for path, types in _schema(entry).items():
            fields[path].update(types)
    table = Table(title=f"{label} schema ({len(fields)} paths)", show_lines=False)
    table.add_column("Field path", style="cyan")
    table.add_column("Observed type", style="green")
    for path in sorted(fields):
        table.add_row(path, "|".join(sorted(fields[path])))
    _console.print(table)


def _field_name(issue: dict[str, Any], field: str) -> str:
    value = issue.get(field)
    if isinstance(value, dict):
        for name_key in ("name", "full_name", "title"):
            name = value.get(name_key)
            if name:
                return str(name)
    elif value:
        return str(value)
    return "unknown"


def _print_entries(domain: str, entries: list[dict[str, Any]]) -> None:
    table = Table(title=f"Tickets ({len(entries)})", show_lines=False)
    table.add_column("ID", style="bold cyan", no_wrap=True)
    table.add_column("Company", style="green")
    table.add_column("Contact", style="green")
    table.add_column("Title")
    urls: list[tuple[Any, str]] = []
    for issue in entries:
        issue_id = issue.get("id")
        url = f"{domain.rstrip('/')}/issues/{issue_id}"
        table.add_row(
            f"#{issue_id}",
            _field_name(issue, "company"),
            _field_name(issue, "contact"),
            str(issue.get("title", "")),
        )
        urls.append((issue_id, url))
    _console.print(table)
    for issue_id, url in urls:
        _console.print(f"#{issue_id}: {url}", style="blue", soft_wrap=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run bounded Okdesk report diagnostics"
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="print one merged issue-entry schema after the report queries",
    )
    args = parser.parse_args()

    domain = os.environ["OKDESK_DOMAIN"]
    token = os.environ["OKDESK_API_TOKEN"]
    client = OkdeskClient(domain, token)
    critical_hours = _env_int("CRITICAL_HOURS", _DEFAULT_CRITICAL_HOURS)
    unanswered_hours = _env_int("UNANSWERED_HOURS", _DEFAULT_UNANSWERED_HOURS)
    page_size = _env_int("PAGE_SIZE", _DEFAULT_PAGE_SIZE, maximum=50)
    company_category_id = os.getenv(
        "COMPANY_CATEGORY_ID", _DEFAULT_COMPANY_CATEGORY_ID
    ).strip()
    if not company_category_id:
        raise ValueError("COMPANY_CATEGORY_ID must not be empty")

    _console.print(
        f"parameters: critical_hours={critical_hours}, "
        f"unanswered_hours={unanswered_hours}, page_size={page_size}, "
        f"company_category_id={company_category_id}"
    )
    _console.rule(f"[bold]Critical tickets (last {critical_hours}h), page 1[/bold]")
    started = time.perf_counter()
    critical = client.list_issues(
        priority_codes=["Critical"],
        company_category_ids=[company_category_id],
        created_since=_cutoff(critical_hours),
        page_size=page_size,
    )
    _console.print(
        f"count on page 1: {len(critical)} (page_size={page_size}; "
        f"more may exist if this is {page_size})"
    )
    _console.print(f"request time: {_elapsed(started):.3f}s", style="yellow")
    _print_entries(domain, critical)

    _console.rule("[bold]Active statuses[/bold]")
    started = time.perf_counter()
    statuses = client.list_issue_statuses()
    active_codes = [s["code"] for s in statuses if not s.get("final", False)]
    _console.print(
        f"active status codes: {len(active_codes)} of {len(statuses)} total; "
        f"request time: {_elapsed(started):.3f}s"
    )

    _console.rule(
        f"[bold]Unanswered candidates (active + without_answer, "
        f"strict age target {unanswered_hours}h), page 1[/bold]"
    )
    started = time.perf_counter()
    candidates = client.list_issues(
        status_codes=active_codes,
        company_category_ids=[company_category_id],
        without_answer=True,
        page_size=page_size,
    )
    unanswered_cutoff = datetime.now(UTC) - timedelta(hours=unanswered_hours)
    strict_unanswered: list[dict[str, Any]] = []
    for issue in candidates:
        issue_id = issue.get("id")
        if isinstance(issue_id, int) and _is_strict_unanswered(
            issue, client.list_issue_comments(issue_id), unanswered_cutoff
        ):
            strict_unanswered.append(issue)
    _console.print(
        f"candidate count on page 1: {len(candidates)}; "
        f"strict unanswered count: {len(strict_unanswered)} "
        f"(page_size={page_size}; more candidates may exist if this is {page_size})"
    )
    _console.print(f"request time: {_elapsed(started):.3f}s", style="yellow")
    _print_entries(domain, strict_unanswered)
    if args.schema:
        _print_schema("issue entry", [*critical, *strict_unanswered])


if __name__ == "__main__":
    main()
