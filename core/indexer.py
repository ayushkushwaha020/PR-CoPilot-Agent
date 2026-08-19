from __future__ import annotations
import hashlib,logging,os,tarfile,tempfile
from pathlib import Path
import chromadb,requests
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from sentence_transformers import SentenceTransformer
logger=logging.getLogger(__name__)
CODE_EXTENSIONS={".py",".js",".ts",".jsx",".tsx",".java",".cpp",".c",".h",".hpp",".go",".rs",".rb",".php",".swift",".kt",".kts",".cs",".scala",".sql",".html",".css",".vue"}
SKIP_DIRS={".git",".github",".venv","venv","node_modules","__pycache__",".idea",".vscode","dist","build","target","coverage"}
class RepositoryIndexer:
    def __init__(self,db_path,github_token="",collection_prefix="pr_copilot",embedding_model="sentence-transformers/all-MiniLM-L6-v2",chunk_size=1200,chunk_overlap=200):
        self.db_path=Path(db_path); self.db_path.mkdir(parents=True,exist_ok=True); self.github_token=github_token; self.collection_prefix=collection_prefix; self.chunker=SentenceSplitter(chunk_size=chunk_size,chunk_overlap=chunk_overlap); self.embedding_model=SentenceTransformer(embedding_model); self.chroma=chromadb.PersistentClient(path=str(self.db_path)); self._collections={}
    def _collection_name(self,repo_name): return f"{self.collection_prefix}_{hashlib.sha1(repo_name.encode()).hexdigest()[:16]}"
    def _collection(self,repo_name,recreate=False):
        name=self._collection_name(repo_name)
        if recreate:
            try:self.chroma.delete_collection(name)
            except Exception:pass
            self._collections.pop(repo_name,None)
        if repo_name not in self._collections:self._collections[repo_name]=self.chroma.get_or_create_collection(name=name,metadata={"repo_name":repo_name})
        return self._collections[repo_name]
    def index_repository(self,repo_name,branch="main",repo_url=None):
        url=f"https://api.github.com/repos/{repo_name}/tarball/{branch}"
        with tempfile.TemporaryDirectory(prefix="prcopilot-") as temp:
            archive=Path(temp)/"repo.tar.gz"; root=Path(temp)/"repo"; root.mkdir(); self._download(url,archive); self._safe_extract(archive,root); repo_root=next((p for p in root.iterdir() if p.is_dir()),root); chunks=self._extract_chunks(repo_root)
        if not chunks: raise RuntimeError(f"No supported source files found in {repo_name}@{branch}")
        col=self._collection(repo_name,recreate=True); docs=[x["content"] for x in chunks]; vectors=self.embedding_model.encode(docs,normalize_embeddings=True,show_progress_bar=False).tolist(); ids=[hashlib.sha1(f"{x['file']}:{x['start_line']}:{i}".encode()).hexdigest() for i,x in enumerate(chunks)]; metas=[{"repo":repo_name,"file":x["file"],"language":x["language"],"start_line":x["start_line"],"end_line":x["end_line"]} for x in chunks]
        for i in range(0,len(ids),100): col.add(ids=ids[i:i+100],documents=docs[i:i+100],embeddings=vectors[i:i+100],metadatas=metas[i:i+100])
        return {"status":"success","chunks":len(chunks),"collection":col.name}
    def get_context(self,repo_name,query,top_k=6):
        col=self._collection(repo_name)
        if col.count()==0:return {"status":"not_indexed","chunks":[]}
        q=self.embedding_model.encode([query or "code review context"],normalize_embeddings=True,show_progress_bar=False).tolist(); r=col.query(query_embeddings=q,n_results=min(top_k,col.count()),include=["documents","metadatas","distances"]); chunks=[]
        for doc,meta,distance in zip(r["documents"][0],r["metadatas"][0],r["distances"][0]): chunks.append({"file":meta["file"],"language":meta["language"],"start_line":meta["start_line"],"end_line":meta["end_line"],"content":doc,"distance":distance})
        return {"status":"success","repository":repo_name,"query":query,"chunks":chunks,"count":len(chunks)}
    def clear_repository_index(self,repo_name):
        try:self.chroma.delete_collection(self._collection_name(repo_name)); self._collections.pop(repo_name,None); return True
        except Exception:return False
    def _download(self,url,destination):
        headers={"Accept":"application/vnd.github+json"}
        if self.github_token:headers["Authorization"]=f"Bearer {self.github_token}"
        with requests.get(url,headers=headers,stream=True,timeout=60) as r:
            r.raise_for_status()
            with destination.open("wb") as out:
                for chunk in r.iter_content(1024*1024):
                    if chunk:out.write(chunk)
    @staticmethod
    def _safe_extract(archive,destination):
        root=destination.resolve()
        with tarfile.open(archive,"r:gz") as tar:
            for m in tar.getmembers():
                target=(destination/m.name).resolve()
                if os.path.commonpath([str(root),str(target)])!=str(root):raise RuntimeError("Unsafe archive path")
            tar.extractall(destination)
    def _extract_chunks(self,repo_root):
        chunks=[]
        for path in repo_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_EXTENSIONS:continue
            if any(part in SKIP_DIRS for part in path.parts):continue
            try:text=path.read_text(encoding="utf-8",errors="replace")
            except OSError:continue
            try:nodes=self.chunker.get_nodes_from_documents([Document(text=text)])
            except Exception as exc:logger.debug("Could not chunk %s: %s",path,exc);continue
            rel=path.relative_to(repo_root).as_posix(); cursor=1
            for node in nodes:
                content=node.get_content()
                if not content.strip():continue
                start=cursor; end=start+content.count("\n"); chunks.append({"file":rel,"language":path.suffix[1:],"content":content,"start_line":start,"end_line":end}); cursor=end+1
        return chunks
