import hashlib,hmac
from core.database import ReviewDatabase
from main import verify_github_webhook

def test_webhook_signature(monkeypatch):
    import config
    secret="test-secret"; monkeypatch.setattr(config,"GITHUB_WEBHOOK_SECRET",secret)
    body=b'{"hello":"world"}'
    sig="sha256="+hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    assert verify_github_webhook({"x-hub-signature-256":sig},body)
    assert not verify_github_webhook({"x-hub-signature-256":"sha256=bad"},body)

def test_database(tmp_path):
    db=ReviewDatabase(str(tmp_path/"review.db"))
    assert db.claim_delivery("abc"); assert not db.claim_delivery("abc")
    rid=db.create_review("abc","owner/repo",1,"Test","sha","issues_found",{"security":[{"file":"app.py","line":3,"severity":"high","message":"Unsafe input","fix":"Validate"}]})
    assert rid==1 and db.stats()["findings"]==1
