from datetime import UTC, datetime

import httpx

from okdesk_mcp.client import OkdeskClient
from okdesk_mcp.reports import (
    fetch_critical_tickets,
    fetch_strict_unanswered_tickets,
    is_strict_unanswered,
)


def test_strict_unanswered_rejects_recent_customer_comment() -> None:
    issue = {"author": {"type": "contact"}, "created_at": "2026-09-01T10:00:00+03:00"}
    comments = [
        {
            "published_at": "2026-09-04T11:12:01+03:00",
            "author": {"type": "contact"},
        }
    ]

    assert not is_strict_unanswered(
        issue, comments, datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    )


def test_strict_unanswered_accepts_oldest_latest_customer_comment() -> None:
    issue = {"author": {"type": "contact"}, "created_at": "2026-09-01T10:00:00+03:00"}
    comments = [
        {
            "published_at": "2026-09-01T12:00:00+03:00",
            "author": {"type": "contact"},
        }
    ]

    assert is_strict_unanswered(
        issue, comments, datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    )


def test_strict_unanswered_rejects_latest_employee_comment() -> None:
    issue = {"author": {"type": "contact"}, "created_at": "2026-09-01T10:00:00+03:00"}
    comments = [
        {
            "published_at": "2026-09-01T12:00:00+03:00",
            "author": {"type": "employee"},
        }
    ]

    assert not is_strict_unanswered(
        issue, comments, datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    )


def test_fetch_critical_tickets_forwards_category_and_cutoff() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get_list("priority_codes[]") == ["Critical"]
        assert request.url.params.get_list("company_category_ids[]") == ["13"]
        assert request.url.params["created_since"] == "03-09-2026 00:00"
        return httpx.Response(200, json=[{"id": 1}])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    issues = fetch_critical_tickets(
        client,
        now=datetime(2026, 9, 4, 0, 0, tzinfo=UTC),
        hours=24,
        company_category_ids=["13"],
    )

    assert issues == [{"id": 1}]


def test_fetch_strict_unanswered_tickets_paginates_until_short_page() -> None:
    pages = {
        1: [{"id": i} for i in range(2)],
        2: [{"id": i} for i in range(2, 3)],
    }
    comments_by_id = {
        0: [
            {"published_at": "2026-09-01T00:00:00+00:00", "author": {"type": "contact"}}
        ],
        1: [
            {"published_at": "2026-09-03T23:00:00+00:00", "author": {"type": "contact"}}
        ],
        2: [
            {
                "published_at": "2026-09-01T00:00:00+00:00",
                "author": {"type": "employee"},
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/issues/list":
            page = int(request.url.params["page[number]"])
            return httpx.Response(200, json=pages.get(page, []))
        issue_id = int(request.url.path.split("/")[4])
        return httpx.Response(200, json=comments_by_id[issue_id])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    result = fetch_strict_unanswered_tickets(
        client,
        now=datetime(2026, 9, 4, 0, 0, tzinfo=UTC),
        hours=48,
        company_category_ids=["13"],
        active_status_codes=["opened"],
        page_size=2,
    )

    # id=0: old contact comment -> included. id=1: contact comment within 48h -> excluded.
    # id=2: latest is employee -> excluded.
    assert [issue["id"] for issue in result.issues] == [0]
    assert result.pages_fetched == 2
    assert result.truncated is False


def test_fetch_strict_unanswered_tickets_marks_truncated_at_max_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/issues/list":
            return httpx.Response(200, json=[{"id": 1}, {"id": 2}])
        return httpx.Response(200, json=[])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    result = fetch_strict_unanswered_tickets(
        client,
        now=datetime(2026, 9, 4, 0, 0, tzinfo=UTC),
        hours=48,
        company_category_ids=["13"],
        active_status_codes=["opened"],
        page_size=2,
        max_pages=2,
    )

    assert result.pages_fetched == 2
    assert result.truncated is True
