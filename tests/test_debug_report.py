import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from debug_report import _is_strict_unanswered


def test_strict_unanswered_rejects_recent_customer_comment() -> None:
    issue = {"author": {"type": "contact"}, "created_at": "2026-09-01T10:00:00+03:00"}
    comments = [
        {
            "published_at": "2026-09-04T11:12:01+03:00",
            "author": {"type": "contact"},
        }
    ]

    assert not _is_strict_unanswered(
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

    assert _is_strict_unanswered(
        issue, comments, datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    )
