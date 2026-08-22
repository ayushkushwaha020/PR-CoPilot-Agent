import pytest

from core.github_client import GitHubClient


def test_require_without_token():
    client = GitHubClient("")
    
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN is not configured"):
        client._require()


def test_changed_lines_by_file_single_hunk():
    class FakeFile:
        filename = "app.py"
        patch = """@@ -1,4 +1,5 @@
 old_line
+new_line
 unchanged
+another_new_line
 end
 """

    class FakePR:
        def get_files(self):
            return [FakeFile()]

    result = GitHubClient._changed_lines_by_file(FakePR())

    assert result == {
        "app.py": {2, 4}
    }


def test_changed_lines_by_file_multiple_files_and_hunks():
    class FileOne:
        filename = "app.py"
        patch = """@@ -10,2 +10,3 @@
 old
+added
 same
 """

    class FileTwo:
        filename = "service.py"
        patch = """@@ -20,3 +20,4 @@
 first
 second
+third
 fourth
@@ -30,2 +31,3 @@
 old
+new
 end
 """

    class FakePR:
        def get_files(self):
            return [FileOne(), FileTwo()]

    result = GitHubClient._changed_lines_by_file(FakePR())

    assert result["app.py"] == {11}
    assert result["service.py"] == {22, 32}


def test_changed_lines_ignores_diff_headers_and_deleted_lines():
    class FakeFile:
        filename = "app.py"
        patch = """@@ -1,4 +1,4 @@
-old
+new
 context
-old_again
+new_again
 """

    class FakePR:
        def get_files(self):
            return [FakeFile()]

    result = GitHubClient._changed_lines_by_file(FakePR())

    assert result["app.py"] == {1, 3}


def test_body_with_fix():
    finding = {
        "severity": "high",
        "agent": "security",
        "message": "Unsafe input",
        "fix": "Validate the input",
    }

    body = GitHubClient._body(finding)

    assert "HIGH" in body
    assert "Security Agent" in body
    assert "Unsafe input" in body
    assert "Suggested fix" in body
    assert "Validate the input" in body


def test_body_without_fix():
    finding = {
        "severity": "medium",
        "agent": "performance",
        "message": "Repeated database query",
        "fix": "",
    }

    body = GitHubClient._body(finding)

    assert "MEDIUM" in body
    assert "Performance Agent" in body
    assert "Repeated database query" in body
    assert "Suggested fix" not in body
