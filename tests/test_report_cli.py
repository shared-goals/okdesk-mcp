import json

import httpx
import pytest

from okdesk_mcp import report_cli


def test_cli_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OKDESK_DOMAIN", raising=False)
    monkeypatch.delenv("OKDESK_API_TOKEN", raising=False)

    with pytest.raises(Exception, match="OKDESK_DOMAIN"):
        report_cli.main(["critical"])


def test_cli_prints_json_for_critical_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OKDESK_DOMAIN", "https://example.okdesk.ru")
    monkeypatch.setenv("OKDESK_API_TOKEN", "test-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1}])

    monkeypatch.setattr(
        report_cli,
        "_client",
        lambda: report_cli.OkdeskClient(
            "https://example.okdesk.ru",
            "test-token",
            httpx.MockTransport(handler),
        ),
    )

    exit_code = report_cli.main(
        ["critical", "--company-category-id", "13", "--hours", "24"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["report"] == "critical"
    assert payload["count"] == 1
    assert payload["issues"] == [{"id": 1}]
