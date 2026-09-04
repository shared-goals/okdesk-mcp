import httpx
import pytest

from okdesk_mcp.client import OkdeskClient, OkdeskError


def test_list_issues_forwards_documented_filters_and_returns_issues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/issues/list"
        assert list(request.url.params.multi_items()) == [
            ("api_token", "test-token"),
            ("priority_codes[]", "Critical"),
            ("created_since", "2026-09-01 00:00"),
            ("updated_until", "2026-09-01 00:00"),
            ("without_answer", "true"),
            ("page[number]", "1"),
            ("page[size]", "50"),
        ]
        return httpx.Response(200, json=[{"id": 42, "title": "Urgent"}])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issues(
        priority_codes=["Critical"],
        created_since="2026-09-01 00:00",
        updated_until="2026-09-01 00:00",
        without_answer=True,
    ) == [{"id": 42, "title": "Urgent"}]


def test_get_issue_returns_the_issue_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/issues/42"
        assert request.url.params["api_token"] == "test-token"
        return httpx.Response(200, json={"id": 42, "title": "Urgent"})

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.get_issue(42) == {"id": 42, "title": "Urgent"}


def test_list_issue_priorities_returns_priority_definitions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/issues/priorities/"
        assert request.url.params["api_token"] == "test-token"
        return httpx.Response(200, json=[{"code": "Critical", "name": "Critical"}])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issue_priorities() == [{"code": "Critical", "name": "Critical"}]


def test_list_issues_forwards_status_codes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert list(request.url.params.get_list("status_codes[]")) == [
            "opened",
            "inprogress",
        ]
        return httpx.Response(200, json=[])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issues(status_codes=["opened", "inprogress"]) == []


def test_list_issue_statuses_returns_status_definitions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/issues/statuses/"
        assert request.url.params["api_token"] == "test-token"
        return httpx.Response(200, json=[{"code": "opened", "final": False}])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issue_statuses() == [{"code": "opened", "final": False}]


def test_list_issue_comments_returns_comment_history() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/issues/42/comments"
        assert request.url.params["api_token"] == "test-token"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 3,
                    "published_at": "2026-09-01T12:00:00+03:00",
                    "author": {"type": "contact"},
                }
            ],
        )

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issue_comments(42) == [
        {
            "id": 3,
            "published_at": "2026-09-01T12:00:00+03:00",
            "author": {"type": "contact"},
        }
    ]


def test_list_issues_reads_a_single_page_by_default() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["page[number]"] == "1"
        assert request.url.params["page[size]"] == "50"
        return httpx.Response(200, json=[{"id": issue_id} for issue_id in range(50)])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    # Even a full 50-item page is returned as-is; the caller decides whether to
    # request page=2. list_issues never loops internally.
    assert client.list_issues() == [{"id": issue_id} for issue_id in range(50)]


def test_list_issues_forwards_explicit_page_and_page_size() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["page[number]"] == "2"
        assert request.url.params["page[size]"] == "10"
        return httpx.Response(200, json=[])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issues(page=2, page_size=10) == []


def test_list_issues_rejects_page_size_above_okdesk_maximum() -> None:
    client = OkdeskClient(
        "https://example.okdesk.ru",
        "test-token",
        httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )

    with pytest.raises(OkdeskError, match="page_size"):
        client.list_issues(page_size=51)


def test_critical_tickets_report_scenario() -> None:
    """Contract test for the 'critical tickets in the last N hours' report:
    filter by the Critical priority code and a created_since cutoff."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get_list("priority_codes[]") == ["Critical"]
        assert request.url.params["created_since"] == "03-09-2026 00:00"
        return httpx.Response(200, json=[{"id": 1, "priority": {"code": "Critical"}}])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issues(
        priority_codes=["Critical"], created_since="03-09-2026 00:00"
    ) == [{"id": 1, "priority": {"code": "Critical"}}]


def test_unanswered_candidates_report_scenario() -> None:
    """Contract test for the 'unanswered client questions' candidate query:
    filter by active status codes and without_answer=true. The stricter
    last-item/author check happens per-issue via list_issue_comments in the
    calling skill, not here."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get_list("status_codes[]") == ["opened", "inprogress"]
        assert request.url.params["without_answer"] == "true"
        return httpx.Response(200, json=[{"id": 7, "without_answer": True}])

    client = OkdeskClient(
        "https://example.okdesk.ru", "test-token", httpx.MockTransport(handler)
    )

    assert client.list_issues(
        status_codes=["opened", "inprogress"], without_answer=True
    ) == [{"id": 7, "without_answer": True}]


def test_client_ignores_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1080")

    client = OkdeskClient(
        "https://example.okdesk.ru",
        "test-token",
        httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )

    assert client.list_issues() == []


def test_api_errors_become_okdesk_errors() -> None:
    client = OkdeskClient(
        "https://example.okdesk.ru",
        "test-token",
        httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": "invalid token"})
        ),
    )

    with pytest.raises(OkdeskError, match="HTTP 401"):
        client.list_issues()
