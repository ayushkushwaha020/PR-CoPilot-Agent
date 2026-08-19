#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env. Add credentials, then run again."
  exit 1
fi
echo "API: http://localhost:8000"
echo "UI:  http://localhost:8000/ui/"
echo "Docs: http://localhost:8000/docs"
.venv/bin/python main.py
