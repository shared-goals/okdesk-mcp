import pytest

from okdesk_mcp import server
from okdesk_mcp.client import OkdeskError


def test_tools_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OKDESK_DOMAIN", raising=False)
    monkeypatch.delenv("OKDESK_API_TOKEN", raising=False)

    with pytest.raises(OkdeskError, match="OKDESK_DOMAIN"):
        server.list_issues()


def test_issue_url_uses_configured_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OKDESK_DOMAIN", "https://example.okdesk.ru/")

    assert server.issue_url(42) == "https://example.okdesk.ru/issues/42"


def test_list_issues_forwards_documented_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        def list_issues(self, **kwargs: object) -> list[dict[str, object]]:
            assert kwargs == {
                "status_codes": None,
                "priority_codes": ["Critical"],
                "created_since": "2026-09-01 00:00",
                "updated_until": "2026-09-02 00:00",
                "without_answer": True,
                "page": 1,
                "page_size": 50,
            }
            return [{"id": 42}]

    monkeypatch.setattr(server, "_client", lambda: Client())

    assert server.list_issues(
        priority_codes=["Critical"],
        created_since="2026-09-01 00:00",
        updated_until="2026-09-02 00:00",
        without_answer=True,
    ) == [{"id": 42}]


def test_list_issue_comments_forwards_issue_id(monkeypatch: pytest.MonkeyPatch) -> None:
    class Client:
        def list_issue_comments(self, issue_id: int) -> list[dict[str, object]]:
            assert issue_id == 42
            return [{"id": 3}]

    monkeypatch.setattr(server, "_client", lambda: Client())

    assert server.list_issue_comments(42) == [{"id": 3}]
