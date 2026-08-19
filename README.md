# PR-CoPilot Agent

Architecture preserved from the academic synopsis:

**GitHub Webhook → FastAPI → PyGithub → LlamaIndex chunking + ChromaDB RAG → parallel Security / Quality & Performance / Architecture agents → LangChain + Gemini → structured findings → GitHub inline review → SQLite → Streamlit**

## What this baseline fixes
- explicit `.env` loading
- webhook delivery idempotency
- asynchronous webhook processing
- private/public GitHub archive access
- LlamaIndex repository chunking
- persistent ChromaDB embeddings
- parallel LangChain/Gemini agents
- five severity levels
- changed-line validation for inline comments
- configurable COMMENT / REQUEST_CHANGES
- SQLite review history and live dashboard metrics

## Windows setup
```powershell
cd F:\.copilot\pr-copilot-agent
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

Dashboard:
```powershell
streamlit run dashboard/app.py
```

API docs: `http://localhost:8000/docs`

## Configuration
Never commit `.env`. Copy `.env.example` to `.env` and provide your GitHub token, webhook secret, and Gemini API key.

`GEMINI_MODEL` is configurable because the Gemini 1.5 Pro model named in the original synopsis is no longer available.
