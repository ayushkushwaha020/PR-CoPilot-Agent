from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT=Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT/".env")

def _bool(name, default): return os.getenv(name,str(default)).strip().lower() in {"1","true","yes","on"}
def _int(name, default):
    try: return int(os.getenv(name,str(default)))
    except ValueError: raise ValueError(f"{name} must be an integer")
def _float(name, default):
    try: return float(os.getenv(name,str(default)))
    except ValueError: raise ValueError(f"{name} must be a number")

GITHUB_TOKEN=os.getenv("GITHUB_TOKEN","")
GITHUB_WEBHOOK_SECRET=os.getenv("GITHUB_WEBHOOK_SECRET","")
GITHUB_WEBHOOK_URL=os.getenv("GITHUB_WEBHOOK_URL","http://localhost:8000/webhook/github")
GEMINI_API_KEY=os.getenv("GEMINI_API_KEY","")
GEMINI_MODEL=os.getenv("GEMINI_MODEL","gemini-2.5-flash")
GEMINI_TEMPERATURE=_float("GEMINI_TEMPERATURE",0.2)
CHROMADB_PATH=os.getenv("CHROMADB_PATH","./chromadb_data")
CHROMADB_COLLECTION_PREFIX=os.getenv("CHROMADB_COLLECTION_PREFIX","pr_copilot")
EMBEDDING_MODEL=os.getenv("EMBEDDING_MODEL","sentence-transformers/all-MiniLM-L6-v2")
RAG_TOP_K=_int("RAG_TOP_K",6); RAG_CHUNK_SIZE=_int("RAG_CHUNK_SIZE",1200); RAG_CHUNK_OVERLAP=_int("RAG_CHUNK_OVERLAP",200)
MAX_DIFF_SIZE_MB=_int("MAX_DIFF_SIZE_MB",5); MAX_FILES_PER_REVIEW=_int("MAX_FILES_PER_REVIEW",200); MAX_INLINE_COMMENTS=_int("MAX_INLINE_COMMENTS",30)
ENABLE_SECURITY_AGENT=_bool("ENABLE_SECURITY_AGENT",True); ENABLE_PERFORMANCE_AGENT=_bool("ENABLE_PERFORMANCE_AGENT",True); ENABLE_ARCHITECTURE_AGENT=_bool("ENABLE_ARCHITECTURE_AGENT",True)
REVIEW_EVENT=os.getenv("REVIEW_EVENT","COMMENT").upper(); ALLOW_REQUEST_CHANGES=_bool("ALLOW_REQUEST_CHANGES",True)
DATABASE_PATH=os.getenv("DATABASE_PATH","./data/pr_copilot.db")
SERVER_HOST=os.getenv("SERVER_HOST","0.0.0.0"); SERVER_PORT=_int("SERVER_PORT",8000); LOG_LEVEL=os.getenv("LOG_LEVEL","INFO").upper()

def validate_config():
    missing=[]
    for name,value in (("GITHUB_TOKEN",GITHUB_TOKEN),("GITHUB_WEBHOOK_SECRET",GITHUB_WEBHOOK_SECRET),("GEMINI_API_KEY",GEMINI_API_KEY)):
        if not value: missing.append(name)
    if REVIEW_EVENT not in {"COMMENT","REQUEST_CHANGES"}: missing.append("REVIEW_EVENT must be COMMENT or REQUEST_CHANGES")
    return missing
