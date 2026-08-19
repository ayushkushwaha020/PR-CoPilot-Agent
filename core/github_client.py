from __future__ import annotations
import logging,re
from github import Github
logger=logging.getLogger(__name__)
HUNK_RE=re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
class GitHubClient:
    def __init__(self,token): self.github=Github(token) if token else None
    def _require(self):
        if not self.github: raise RuntimeError("GITHUB_TOKEN is not configured")
    def fetch_pr_diff(self,repo_name,pr_number):
        self._require()
        try:
            repo=self.github.get_repo(repo_name); pr=repo.get_pull(pr_number)
            return {"pr_number":pr.number,"title":pr.title,"author":pr.user.login,"created_at":pr.created_at.isoformat() if pr.created_at else None,"updated_at":pr.updated_at.isoformat() if pr.updated_at else None,"changed_files":pr.changed_files,"base_branch":pr.base.ref,"head_sha":pr.head.sha,"files":[{"filename":f.filename,"status":f.status,"additions":f.additions,"deletions":f.deletions,"changes":f.changes,"patch":f.patch or "","blob_url":f.blob_url} for f in pr.get_files()]}
        except Exception: logger.exception("Could not fetch PR diff for %s#%s",repo_name,pr_number); return None
    def post_review(self,repo_name,pr_number,review_results,event="COMMENT",max_inline_comments=30):
        self._require(); repo=self.github.get_repo(repo_name); pr=repo.get_pull(pr_number); commits=pr.get_commits(); commit=commits.get_page(commits.totalCount-1)[0] if commits.totalCount else pr.get_commits()[0]
        changed=self._changed_lines_by_file(pr); comments=[]; all_findings=[]; summary=["## 🤖 PR-CoPilot Agent Review",""]
        for agent,findings in review_results.items():
            if not findings: continue
            summary.append(f"### { {'security':'🔒 Security','performance':'⚡ Quality & Performance','architecture':'🏗️ Architecture'}.get(agent,agent.title())}")
            for x in findings:
                all_findings.append(x); summary.append(f"- **{x['severity'].upper()}** `{x['file']}:{x['line']}` — {x['message']}")
                if x.get("fix"): summary.append(f"  - Fix: {x['fix']}")
                if x["file"] in changed and x["line"] in changed[x["file"]]: comments.append({"path":x["file"],"line":x["line"],"side":"RIGHT","body":self._body(x)})
            summary.append("")
        if not all_findings: summary.append("✅ No defensible issues were detected by the enabled agents.")
        elif not comments: summary.append("ℹ️ Findings remain in the summary because the model did not target a changed line.")
        comments=comments[:max_inline_comments]; review=pr.create_review(commit=commit,body="\n".join(summary),event=event,comments=comments)
        return {"review_id":review.id,"inline_comments":len(comments),"findings":len(all_findings),"event":event}
    @staticmethod
    def _body(x):
        icon={"critical":"🚨","high":"🔴","medium":"🟠","low":"🟡","info":"ℹ️"}[x["severity"]]; text=f"{icon} **{x['severity'].upper()} — {x['agent'].title()} Agent**\n\n{x['message']}"; return text+(f"\n\n**Suggested fix:** {x['fix']}" if x.get("fix") else "")
    @staticmethod
    def _changed_lines_by_file(pr):
        result={}
        for f in pr.get_files():
            patch=f.patch or ""; result.setdefault(f.filename,set()); new_line=0
            for raw in patch.splitlines():
                m=HUNK_RE.match(raw)
                if m: new_line=int(m.group(2)); continue
                if raw.startswith("+") and not raw.startswith("+++"): result[f.filename].add(new_line); new_line+=1
                elif raw.startswith("-") and not raw.startswith("---"): continue
                elif new_line: new_line+=1
        return result
    def get_repository_metadata(self,repo_name):
        self._require()
        try:
            r=self.github.get_repo(repo_name); return {"name":r.name,"full_name":r.full_name,"description":r.description,"language":r.language,"topics":r.topics,"url":r.html_url,"clone_url":r.clone_url,"default_branch":r.default_branch}
        except Exception: logger.exception("Could not fetch repository metadata"); return None
