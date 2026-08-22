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


def test_process_pull_request_happy_path(monkeypatch):
    import main

    diff = {
        "files": [
            {
                "filename": "app.py",
                "patch": """@@ -1,1 +1,2 @@
+new_line
""",
            }
        ]
    }

    context = {
        "status": "success",
        "chunks": [],
    }

    results = {
        "security": [
            {
                "agent": "security",
                "file": "app.py",
                "line": 1,
                "severity": "high",
                "message": "Unsafe input",
                "fix": "Validate input",
            }
        ],
        "performance": [],
        "architecture": [],
    }

    posted = {
        "review_id": 123,
        "inline_comments": 1,
        "findings": 1,
        "event": "COMMENT",
    }

    class FakeIndexer:
        def index_repository(self, repo_name, branch, repo_url=None):
            assert repo_name == "owner/repo"
            assert branch == "main"
            assert repo_url == "https://github.com/owner/repo.git"

        def get_context(self, repo_name, query, top_k):
            assert repo_name == "owner/repo"
            assert top_k == main.config.RAG_TOP_K
            return context

    class FakeEngine:
        def orchestrate_review(self, received_diff, received_context, metadata):
            assert received_diff == diff
            assert received_context == context
            assert metadata["number"] == 1
            assert metadata["title"] == "Test PR"
            assert metadata["repo"] == "owner/repo"
            assert metadata["head_sha"] == "abc123"
            return results

    class FakeGitHub:
        def fetch_pr_diff(self, repo_name, pr_number):
            assert repo_name == "owner/repo"
            assert pr_number == 1
            return diff

        def post_review(
            self,
            repo_name,
            pr_number,
            review_results,
            event,
            max_inline_comments,
        ):
            assert repo_name == "owner/repo"
            assert pr_number == 1
            assert review_results == results
            assert event == "COMMENT"
            assert max_inline_comments == main.config.MAX_INLINE_COMMENTS
            return posted

    class FakeDB:
        def create_review(
            self,
            delivery_id,
            repo_name,
            pr_number,
            pr_title,
            commit_sha,
            status,
            findings,
        ):
            assert delivery_id == "delivery-1"
            assert repo_name == "owner/repo"
            assert pr_number == 1
            assert pr_title == "Test PR"
            assert commit_sha == "abc123"
            assert status == "issues_found"
            assert findings == results
            return 1

    monkeypatch.setattr(main, "github_client", FakeGitHub())
    monkeypatch.setattr(main, "db", FakeDB())
    monkeypatch.setattr(main, "get_indexer", lambda: FakeIndexer())
    monkeypatch.setattr(main, "get_review_engine", lambda: FakeEngine())

    main.process_pull_request(
        "delivery-1",
        "owner/repo",
        1,
        "Test PR",
        "https://github.com/owner/repo.git",
        "main",
        "abc123",
    )
