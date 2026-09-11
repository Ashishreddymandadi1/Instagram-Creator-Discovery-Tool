#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python -m venv .venv
if [ -f .venv/Scripts/activate ]; then source .venv/Scripts/activate; else source .venv/bin/activate; fi
pip install -q -r requirements.txt
[ -f .env ] || { echo "Create backend/.env from backend/.env.example first."; exit 1; }
exec uvicorn app.main:app --reload --port 8000
