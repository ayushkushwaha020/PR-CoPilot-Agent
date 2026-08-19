from __future__ import annotations
import hashlib,hmac,json,logging
from pathlib import Path
from fastapi import BackgroundTasks,FastAPI,HTTPException,Request
from fastapi.staticfiles import StaticFiles
import config
from core.ai_agent import AgenticReviewEngine
from core.database import ReviewDatabase
from core.github_client import GitHubClient
from core.indexer import RepositoryIndexer

logging.basicConfig(level=getattr(logging,config.LOG_LEVEL,logging.INFO),format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger=logging.getLogger("pr-copilot")
app=FastAPI(title="PR-CoPilot Agent",description="Autonomous AI-powered GitHub pull-request reviewer",version="1.1.0")
db=ReviewDatabase(config.DATABASE_PATH); github_client=GitHubClient(config.GITHUB_TOKEN)
_indexer=None; _review_engine=None

def get_indexer():
    global _indexer
    if _indexer is None:
        _indexer=RepositoryIndexer(config.CHROMADB_PATH,github_token=config.GITHUB_TOKEN,collection_prefix=config.CHROMADB_COLLECTION_PREFIX,embedding_model=config.EMBEDDING_MODEL,chunk_size=config.RAG_CHUNK_SIZE,chunk_overlap=config.RAG_CHUNK_OVERLAP)
    return _indexer

def get_review_engine():
    global _review_engine
    if _review_engine is None:
        _review_engine=AgenticReviewEngine(config.GEMINI_API_KEY,config.GEMINI_MODEL,config.GEMINI_TEMPERATURE,{"security":config.ENABLE_SECURITY_AGENT,"performance":config.ENABLE_PERFORMANCE_AGENT,"architecture":config.ENABLE_ARCHITECTURE_AGENT})
    return _review_engine

def verify_github_webhook(headers,payload):
    signature=headers.get("x-hub-signature-256","")
    if not signature or not config.GITHUB_WEBHOOK_SECRET: return False
    expected="sha256="+hmac.new(config.GITHUB_WEBHOOK_SECRET.encode(),payload,hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature,expected)

def _diff_size_mb(diff):
    return sum(len((f.get("patch") or "").encode()) for f in diff.get("files",[]))/(1024*1024)

def process_pull_request(delivery_id,repo_name,pr_number,pr_title,repo_url,base_branch,head_sha):
    diff=github_client.fetch_pr_diff(repo_name,pr_number)
    if not diff: raise RuntimeError("Could not fetch PR diff")
    if _diff_size_mb(diff)>config.MAX_DIFF_SIZE_MB: raise RuntimeError("PR diff exceeds MAX_DIFF_SIZE_MB")
    if len(diff.get("files",[]))>config.MAX_FILES_PER_REVIEW: raise RuntimeError("Too many changed files")
    indexer=get_indexer(); indexer.index_repository(repo_name,base_branch,repo_url=repo_url)
    context=indexer.get_context(repo_name,json.dumps(diff,ensure_ascii=False),config.RAG_TOP_K)
    results=get_review_engine().orchestrate_review(diff,context,{"number":pr_number,"title":pr_title,"repo":repo_name,"head_sha":head_sha})
    total=sum(len(v) for v in results.values()); event=config.REVIEW_EVENT
    if event=="REQUEST_CHANGES" and (not config.ALLOW_REQUEST_CHANGES or not any(x.get("severity") in {"critical","high"} for v in results.values() for x in v)): event="COMMENT"
    posted=github_client.post_review(repo_name,pr_number,results,event,max_inline_comments=config.MAX_INLINE_COMMENTS)
    db.create_review(delivery_id,repo_name,pr_number,pr_title,head_sha,"issues_found" if total else "clean",results)
    logger.info("Review complete: %s#%s findings=%s inline=%s",repo_name,pr_number,total,posted["inline_comments"])

@app.post("/webhook/github",status_code=202)
async def handle_github_webhook(request:Request,background_tasks:BackgroundTasks):
    body=await request.body()
    if not verify_github_webhook(dict(request.headers),body): raise HTTPException(401,"Invalid GitHub webhook signature")
    event=request.headers.get("x-github-event","").lower(); delivery=request.headers.get("x-github-delivery","")
    if event!="pull_request": return {"message":f"Event '{event}' ignored"}
    payload=json.loads(body); action=payload.get("action")
    if action not in {"opened","synchronize","reopened"}: return {"message":f"PR action '{action}' ignored"}
    if delivery and not db.claim_delivery(delivery): return {"message":"Webhook delivery already processed"}
    missing=config.validate_config()
    if missing: raise HTTPException(503,f"Service not configured: {', '.join(missing)}")
    pr=payload.get("pull_request") or {}; repo=payload.get("repository") or {}; repo_name=repo.get("full_name"); number=pr.get("number")
    if not repo_name or not number: raise HTTPException(400,"Malformed pull_request payload")
    background_tasks.add_task(process_pull_request,delivery or f"{repo_name}#{number}",repo_name,int(number),pr.get("title",""),repo.get("clone_url",""),(pr.get("base") or {}).get("ref","main"),(pr.get("head") or {}).get("sha",""))
    return {"message":"PR review queued","repository":repo_name,"pr_number":number}

@app.get("/health")
async def health():
    missing=config.validate_config(); return {"status":"ok" if not missing else "degraded","service":"PR-CoPilot Agent","configuration_missing":missing}
@app.get("/api/stats")
async def stats(): return db.stats()
@app.get("/api/reviews")
async def reviews(limit:int=20): return {"reviews":db.recent_reviews(max(1,min(limit,100)))}
@app.get("/")
async def root(): return {"service":"PR-CoPilot Agent","version":app.version,"endpoints":["/webhook/github","/health","/api/stats","/api/reviews","/docs"]}
frontend_path=Path(__file__).parent/"frontend"
if frontend_path.exists(): app.mount("/ui",StaticFiles(directory=str(frontend_path),html=True),name="frontend")
if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host=config.SERVER_HOST,port=config.SERVER_PORT,log_level=config.LOG_LEVEL.lower())
