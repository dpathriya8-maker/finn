# FINN

Financial Investment Agent for Indian stocks: a mobile-first Morning Brief of what changed in your portfolio, plus research grounded only in company filings.

Status: work in progress. Built for the ENAM AI Engineer Build Challenge.

## Run locally

Backend (Python 3.14, the version Render uses):

```
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn app.main:app --port 8000
.venv/Scripts/python -m pytest                                  # tests
```

Frontend (Node 20.9 or newer):

```
cd frontend
npm install
npm run dev     # http://localhost:3000, talks to http://localhost:8000 by default
```

Copy `.env.example` to `.env` for the keys the backend and pipeline need (never commit it), and run `bash scripts/install-hooks.sh` once in a fresh clone to enable the secret-scan pre-commit hook.

More: [deploying](docs/deploy.md), [decisions](docs/decisions.md), [architecture](docs/architecture.md), [build log](docs/build-log.md).
