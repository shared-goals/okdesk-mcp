"""Deterministic CLI for the critical/unanswered Okdesk reports.

Runs the exact same code as scripts/debug_report.py (via okdesk_mcp.reports),
so any consumer scripting this instead of re-deriving the filter logic from
individual MCP tool calls is guaranteed to see the same dataset. Prints JSON
only — no Rich formatting — so it is safe for a skill or another script to
parse.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime

from .client import OkdeskClient, OkdeskError
from .reports import fetch_critical_tickets, fetch_strict_unanswered_tickets


def _company_category_ids(raw: list[str] | None) -> list[str] | None:
    return raw or None


def _client() -> OkdeskClient:
    domain = os.environ.get("OKDESK_DOMAIN")
    api_token = os.environ.get("OKDESK_API_TOKEN")
    if not domain or not api_token:
        raise OkdeskError("OKDESK_DOMAIN and OKDESK_API_TOKEN must be configured")
    return OkdeskClient(domain, api_token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic Okdesk reports")
    parser.add_argument("report", choices=["critical", "unanswered"])
    parser.add_argument("--company-category-id", action="append", dest="category_ids")
    parser.add_argument("--hours", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args(argv)

    client = _client()
    now = datetime.now(UTC)
    category_ids = _company_category_ids(args.category_ids)

    if args.report == "critical":
        hours = args.hours if args.hours is not None else 24
        issues = fetch_critical_tickets(
            client,
            now=now,
            hours=hours,
            company_category_ids=category_ids,
            page_size=args.page_size,
        )
        payload = {
            "report": "critical",
            "hours": hours,
            "count": len(issues),
            "truncated": len(issues) >= args.page_size,
            "issues": issues,
        }
    else:
        hours = args.hours if args.hours is not None else 48
        result = fetch_strict_unanswered_tickets(
            client,
            now=now,
            hours=hours,
            company_category_ids=category_ids,
            page_size=args.page_size,
            max_pages=args.max_pages,
        )
        payload = {
            "report": "unanswered",
            "hours": hours,
            "count": len(result.issues),
            "pages_fetched": result.pages_fetched,
            "truncated": result.truncated,
            "issues": result.issues,
        }

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
