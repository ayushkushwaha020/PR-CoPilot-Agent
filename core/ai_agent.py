from __future__ import annotations
import json,logging,re
from concurrent.futures import ThreadPoolExecutor,as_completed
from enum import Enum
from langchain_core.messages import HumanMessage,SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
logger=logging.getLogger(__name__); SEVERITIES={"critical","high","medium","low","info"}
class AgentType(str,Enum): SECURITY="security"; PERFORMANCE="performance"; ARCHITECTURE="architecture"
SYSTEM_PROMPTS={AgentType.SECURITY:"""You are the Security Agent. Review ONLY the supplied changed code and repository context. Focus on OWASP Top 10, secrets, injection, auth/authz, unsafe deserialization, path traversal, SSRF, XSS, crypto and data exposure. Do not invent issues. Every finding MUST target a changed line in the new/right side. Return ONLY JSON: {\"findings\":[{\"file\":\"path\",\"line\":123,\"severity\":\"critical|high|medium|low|info\",\"message\":\"...\",\"fix\":\"...\"}]}. Return {\"findings\":[]} if there is no defensible issue.""",AgentType.PERFORMANCE:"""You are the Quality & Performance Agent. Review ONLY changed code and repository context. Focus on complexity, repeated work, inefficient queries, memory growth, blocking operations and allocations. Every finding MUST target a changed line in the new/right side. Return ONLY JSON: {\"findings\":[{\"file\":\"path\",\"line\":123,\"severity\":\"critical|high|medium|low|info\",\"message\":\"...\",\"fix\":\"...\"}]}. Return {\"findings\":[]} if there is no defensible issue.""",AgentType.ARCHITECTURE:"""You are the Architecture Agent. Review ONLY changed code and repository context. Focus on modularity, coupling, SOLID, project patterns, error handling, testability and dependency boundaries. Do not report subjective preferences. Every finding MUST target a changed line in the new/right side. Return ONLY JSON: {\"findings\":[{\"file\":\"path\",\"line\":123,\"severity\":\"critical|high|medium|low|info\",\"message\":\"...\",\"fix\":\"...\"}]}. Return {\"findings\":[]} if there is no defensible issue."""}
class AgenticReviewEngine:
    def __init__(self,api_key,model="gemini-2.5-flash",temperature=0.2,enabled_agents=None):
        if not api_key: raise RuntimeError("GEMINI_API_KEY is not configured")
        self.enabled_agents=enabled_agents or {a.value:True for a in AgentType}; self.llm=ChatGoogleGenerativeAI(model=model,google_api_key=api_key,temperature=temperature,max_retries=2)
    def orchestrate_review(self,diff,repo_context,pr_metadata):
        diff_text=self._format_diff(diff); context_text=self._format_context(repo_context); agents=[a for a in AgentType if self.enabled_agents.get(a.value,True)]; results={a.value:[] for a in AgentType}
        with ThreadPoolExecutor(max_workers=max(1,len(agents))) as pool:
            jobs={pool.submit(self._run_agent,a,diff_text,context_text):a for a in agents}
            for f in as_completed(jobs):
                a=jobs[f]
                try:results[a.value]=f.result()
                except Exception:logger.exception("%s agent failed",a.value)
        return results
    def _run_agent(self,agent,diff_text,context_text):
        response=self.llm.invoke([SystemMessage(content=SYSTEM_PROMPTS[agent]),HumanMessage(content=f"PR DIFF:\n{diff_text}\n\nREPOSITORY CONTEXT:\n{context_text}\n\nJSON ONLY.")]); payload=self._parse_json(self._text(response.content)); return self._normalize(payload.get("findings",[]) if isinstance(payload,dict) else [],agent)
    @staticmethod
    def _text(content):
        if isinstance(content,str):return content
        if isinstance(content,list):return "".join(x if isinstance(x,str) else str(x.get("text","")) for x in content if isinstance(x,(str,dict)))
        return str(content)
    @staticmethod
    def _parse_json(text):
        cleaned=re.sub(r"^```(?:json)?\s*|\s*```$","",text.strip(),flags=re.I)
        try:return json.loads(cleaned)
        except json.JSONDecodeError:
            m=re.search(r"\{.*\}",cleaned,re.S)
            try:return json.loads(m.group(0)) if m else {}
            except json.JSONDecodeError:return {}
    @staticmethod
    def _normalize(items,agent):
        out=[]
        for x in items if isinstance(items,list) else []:
            if not isinstance(x,dict):continue
            try:line=int(x.get("line"))
            except (TypeError,ValueError):continue
            sev=str(x.get("severity","info")).lower(); file=str(x.get("file","")).strip(); msg=str(x.get("message","")).strip()
            if line<1 or sev not in SEVERITIES or not file or not msg:continue
            out.append({"agent":agent.value,"file":file,"line":line,"severity":sev,"message":msg,"fix":str(x.get("fix") or x.get("optimization") or x.get("improvement") or "").strip()})
        return out
    @staticmethod
    def _format_diff(diff):
        return "\n\n".join([f"PR #{diff.get('pr_number')}: {diff.get('title')}"]+[f"FILE: {f.get('filename')}\nSTATUS: {f.get('status')}\nPATCH:\n```diff\n{f.get('patch') or ''}\n```" for f in diff.get("files",[])])
    @staticmethod
    def _format_context(ctx):
        if ctx.get("status")!="success":return "No repository context was retrieved."
        return "\n\n".join(f"FILE: {x.get('file')} lines {x.get('start_line')}-{x.get('end_line')}\n```text\n{x.get('content','')}\n```" for x in ctx.get("chunks",[])) or "No repository context was retrieved."
