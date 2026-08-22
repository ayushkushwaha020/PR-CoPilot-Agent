import hashlib
import hmac

from core.database import ReviewDatabase
from main import verify_github_webhook


def test_webhook_signature(monkeypatch):
    import config

    secret = "test-secret"
    monkeypatch.setattr(config, "GITHUB_WEBHOOK_SECRET", secret)

    body = b'{"hello":"world"}'

    signature = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    assert verify_github_webhook(
        {"x-hub-signature-256": signature},
        body,
    )

    assert not verify_github_webhook(
        {"x-hub-signature-256": "sha256=bad"},
        body,
    )


def test_webhook_signature_missing(monkeypatch):
    import config

    monkeypatch.setattr(
        config,
        "GITHUB_WEBHOOK_SECRET",
        "test-secret",
    )

    body = b'{"hello":"world"}'

    assert not verify_github_webhook({}, body)


def test_webhook_signature_missing_secret(monkeypatch):
    import config

    monkeypatch.setattr(
        config,
        "GITHUB_WEBHOOK_SECRET",
        "",
    )

    body = b'{"hello":"world"}'

    assert not verify_github_webhook(
        {"x-hub-signature-256": "sha256=something"},
        body,
    )


def test_database(tmp_path):
    db = ReviewDatabase(str(tmp_path / "review.db"))

    assert db.claim_delivery("abc")
    assert not db.claim_delivery("abc")

    findings = {
        "security": [
            {
                "file": "app.py",
                "line": 3,
                "severity": "high",
                "message": "Unsafe input",
                "fix": "Validate",
            }
        ]
    }

    review_id = db.create_review(
        "abc",
        "owner/repo",
        1,
        "Test",
        "sha",
        "issues_found",
        findings,
    )

    assert review_id == 1

    stats = db.stats()

    assert stats["reviews"] == 1
    assert stats["findings"] == 1
    assert stats["security"] == 1
    assert stats["performance"] == 0
    assert stats["architecture"] == 0


def test_database_multiple_agents_and_findings(tmp_path):
    db = ReviewDatabase(str(tmp_path / "review.db"))

    findings = {
        "security": [
            {
                "file": "auth.py",
                "line": 10,
                "severity": "critical",
                "message": "Security issue",
                "fix": "Fix authentication",
            }
        ],
        "performance": [
            {
                "file": "api.py",
                "line": 20,
                "severity": "medium",
                "message": "Slow query",
                "optimization": "Add an index",
            }
        ],
        "architecture": [
            {
                "file": "service.py",
                "line": 30,
                "severity": "low",
                "message": "Architecture issue",
                "improvement": "Extract service",
            }
        ],
    }

    review_id = db.create_review(
        "delivery-1",
        "owner/repo",
        2,
        "Multiple findings",
        "abc123",
        "issues_found",
        findings,
    )

    assert review_id == 1

    stats = db.stats()

    assert stats["reviews"] == 1
    assert stats["findings"] == 3
    assert stats["security"] == 1
    assert stats["performance"] == 1
    assert stats["architecture"] == 1


def test_recent_reviews(tmp_path):
    db = ReviewDatabase(str(tmp_path / "review.db"))

    db.create_review(
        "delivery-1",
        "owner/repo",
        1,
        "First PR",
        "sha1",
        "clean",
        {},
    )

    db.create_review(
        "delivery-2",
        "owner/repo",
        2,
        "Second PR",
        "sha2",
        "issues_found",
        {
            "security": [
                {
                    "file": "app.py",
                    "line": 5,
                    "severity": "high",
                    "message": "Issue",
                    "fix": "Fix it",
                }
            ]
        },
    )

    reviews = db.recent_reviews()

    assert len(reviews) == 2
    assert reviews[0]["pr_number"] == 2
    assert reviews[0]["pr_title"] == "Second PR"
    assert reviews[0]["status"] == "issues_found"
    assert reviews[0]["total_findings"] == 1

    assert reviews[1]["pr_number"] == 1
    assert reviews[1]["total_findings"] == 0


def test_recent_reviews_limit(tmp_path):
    db = ReviewDatabase(str(tmp_path / "review.db"))

    for number in range(1, 6):
        db.create_review(
            f"delivery-{number}",
            "owner/repo",
            number,
            f"PR {number}",
            f"sha-{number}",
            "clean",
            {},
        )

    reviews = db.recent_reviews(limit=2)

    assert len(reviews) == 2
    assert reviews[0]["pr_number"] == 5
    assert reviews[1]["pr_number"] == 4