@echo off
setlocal
cd /d "%~dp0"
echo PR-CoPilot Agent
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python 3.14 virtual environment...
  py -3.14 -m venv .venv || exit /b 1
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || exit /b 1
)
if not exist ".env" (
  copy /Y .env.example .env >nul
  echo Created .env. Add your credentials, then run this script again.
  exit /b 1
)
echo API: http://localhost:8000
echo UI:  http://localhost:8000/ui/
echo Docs: http://localhost:8000/docs
".venv\Scripts\python.exe" main.py
