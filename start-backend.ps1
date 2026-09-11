Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt
if (-not (Test-Path .env)) { Write-Error "Create backend\.env from backend\.env.example first."; exit 1 }
uvicorn app.main:app --reload --port 8000
