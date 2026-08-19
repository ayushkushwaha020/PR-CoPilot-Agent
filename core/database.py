from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

class ReviewDatabase:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.initialize()
    @contextmanager
    def connection(self):
        conn=sqlite3.connect(self.path); conn.row_factory=sqlite3.Row
        try: yield conn; conn.commit()
        finally: conn.close()
    def initialize(self):
        with self.connection() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS webhook_deliveries(delivery_id TEXT PRIMARY KEY,received_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,delivery_id TEXT,repo_name TEXT NOT NULL,pr_number INTEGER NOT NULL,pr_title TEXT,commit_sha TEXT,status TEXT NOT NULL,total_findings INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS findings(id INTEGER PRIMARY KEY AUTOINCREMENT,review_id INTEGER NOT NULL,agent TEXT NOT NULL,severity TEXT NOT NULL,file TEXT,line INTEGER,message TEXT NOT NULL,fix TEXT,FOREIGN KEY(review_id) REFERENCES reviews(id));CREATE INDEX IF NOT EXISTS idx_reviews_repo_pr ON reviews(repo_name,pr_number);CREATE INDEX IF NOT EXISTS idx_findings_review ON findings(review_id);""")
    def claim_delivery(self,delivery_id):
        with self.connection() as c:
            try: c.execute("INSERT INTO webhook_deliveries(delivery_id,received_at) VALUES (?,?)",(delivery_id,datetime.now(timezone.utc).isoformat())); return True
            except sqlite3.IntegrityError: return False
    def create_review(self,delivery_id,repo_name,pr_number,pr_title,commit_sha,status,findings):
        flat=[(agent,x) for agent,items in findings.items() for x in items]
        with self.connection() as c:
            cur=c.execute("INSERT INTO reviews(delivery_id,repo_name,pr_number,pr_title,commit_sha,status,total_findings,created_at) VALUES (?,?,?,?,?,?,?,?)",(delivery_id,repo_name,pr_number,pr_title,commit_sha,status,len(flat),datetime.now(timezone.utc).isoformat())); rid=cur.lastrowid
            for agent,x in flat: c.execute("INSERT INTO findings(review_id,agent,severity,file,line,message,fix) VALUES (?,?,?,?,?,?,?)",(rid,agent,x.get("severity","info"),x.get("file"),x.get("line"),x.get("message",""),x.get("fix") or x.get("optimization") or x.get("improvement")))
            return rid
    def stats(self):
        with self.connection() as c: return {"reviews":c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],"findings":c.execute("SELECT COUNT(*) FROM findings").fetchone()[0],"security":c.execute("SELECT COUNT(*) FROM findings WHERE agent='security'").fetchone()[0],"performance":c.execute("SELECT COUNT(*) FROM findings WHERE agent='performance'").fetchone()[0],"architecture":c.execute("SELECT COUNT(*) FROM findings WHERE agent='architecture'").fetchone()[0]}
    def recent_reviews(self,limit=20):
        with self.connection() as c: return [dict(r) for r in c.execute("SELECT id,repo_name,pr_number,pr_title,status,total_findings,created_at FROM reviews ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]
