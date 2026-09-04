"""Minimal HTTP client for the Okdesk REST API."""

from collections.abc import Sequence
from typing import Any

import httpx

_MAX_PAGE_SIZE = 50


class OkdeskError(Exception):
    """Raised when the Okdesk API rejects a request or returns invalid data."""


class OkdeskClient:
    def __init__(
        self, domain: str, api_token: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._domain = domain.rstrip("/")
        self._api_token = api_token
        self._transport = transport

    def list_issues(
        self,
        *,
        status_codes: Sequence[str] | None = None,
        priority_codes: Sequence[str] | None = None,
        company_category_ids: Sequence[str] | None = None,
        created_since: str | None = None,
        updated_until: str | None = None,
        without_answer: bool | None = None,
        page: int = 1,
        page_size: int = _MAX_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        if not 1 <= page_size <= _MAX_PAGE_SIZE:
            raise OkdeskError(f"page_size must be between 1 and {_MAX_PAGE_SIZE}")

        params: list[tuple[str, str]] = []
        if status_codes is not None:
            params.extend(("status_codes[]", code) for code in status_codes)
        if priority_codes is not None:
            params.extend(("priority_codes[]", code) for code in priority_codes)
        if company_category_ids is not None:
            params.extend(
                ("company_category_ids[]", category_id)
                for category_id in company_category_ids
            )
        if created_since is not None:
            params.append(("created_since", created_since))
        if updated_until is not None:
            params.append(("updated_until", updated_until))
        if without_answer is not None:
            params.append(("without_answer", str(without_answer).lower()))
        params.append(("page[number]", str(page)))
        params.append(("page[size]", str(page_size)))

        return self._get_issue_list("/api/v1/issues/list", params)

    def list_issue_priorities(self) -> list[dict[str, Any]]:
        return self._get_issue_list("/api/v1/issues/priorities/", [])

    def list_issue_statuses(self) -> list[dict[str, Any]]:
        return self._get_issue_list("/api/v1/issues/statuses/", [])

    def list_issue_comments(self, issue_id: int) -> list[dict[str, Any]]:
        return self._get_issue_list(f"/api/v1/issues/{issue_id}/comments", [])

    def get_issue(self, issue_id: int) -> dict[str, Any]:
        payload = self._get(f"/api/v1/issues/{issue_id}")
        if not isinstance(payload, dict):
            raise OkdeskError("Okdesk returned an invalid issue response")
        return payload

    def _get_issue_list(
        self, path: str, params: Sequence[tuple[str, str]]
    ) -> list[dict[str, Any]]:
        payload = self._get(path, params)
        if not isinstance(payload, list) or not all(
            isinstance(issue, dict) for issue in payload
        ):
            raise OkdeskError("Okdesk returned an invalid issue list response")
        return payload

    def _get(self, path: str, params: Sequence[tuple[str, str]] | None = None) -> Any:
        request_params = [("api_token", self._api_token), *(params or [])]

        with httpx.Client(
            base_url=self._domain,
            transport=self._transport,
            timeout=20.0,
            trust_env=False,
        ) as client:
            response = client.get(path, params=request_params)

        if response.is_error:
            raise OkdeskError(f"Okdesk API returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise OkdeskError("Okdesk returned invalid JSON") from error
