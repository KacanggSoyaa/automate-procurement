# AGENTS.md

## Project
Automate Procurement: Python (FastAPI) backend + Vite/React/Tailwind frontend. Extracts ITB/RFQ line items via Gemini (or OpenAI/Anthropic), writes a `.docx` spec sheet, drafts an RFQ email. Runs as two processes.

## Commands
- Backend (repo root): `python -m uvicorn server.app:app --reload --port 8000`
- Frontend: `cd web; npm install; npm run dev` (Vite on :5173, proxies `/api` → :8000)
- Frontend prod build: `cd web; npm run build` (output `web/dist`)
- CLI: `python cli.py <cmd>` or `run.bat`/`run.ps1` (which just run `python cli.py`)
- Typecheck frontend: `cd web; npx tsc -b` (part of `npm run build`)
- No test suite exists.

## Setup
- Python 3.10+ (dev on 3.14), Node 18+.
- `python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt`
- `.env` in repo root (gitignored). `GEMINI_API_KEY` required. See `.env.example` for full list (AUTH_SECRET, ALLOWED_ORIGINS, upload limits, etc.).
- `.vscode/settings.json` enables `python.terminal.useEnvFile`, so `.env` is loaded in the integrated terminal.

## Architecture
- `server/app.py` FastAPI app; `server/jobs.py` job manager; `server/pipeline.py` end-to-end extraction+generation (shared by API and CLI); `server/history.py` persisted runs.
- `extractors/` PDF + Office (docx/xlsx/xlsm).
- `processors/ai_processor.py` Gemini classification; `server/ai_providers.py` multi-provider (gemini/openai/anthropic).
- `generators/` spec sheet, RFQ email, dispatcher.
- `cli.py` Click entry point.
- `config/settings.yaml` paths + defaults.
- `web/src` React UI.

## Conventions / Gotchas
- Backend must be started from repo root so `ROOT`/paths resolve; pipeline inserts repo root into `sys.path`.
- Free-tier Gemini quota ~20 req/day per model; processor falls back through models and caches in `data/.ai_cache/` (gitignored). Repeat runs cost no quota.
- `data/`, `outputs/` hold confidential bid docs and are gitignored — never commit.
- `AUTH_SECRET` signs sessions and encrypts saved AI keys; changing it signs everyone out and makes stored keys unreadable.
- CLI `extract` default pattern is `*ITB*`; PDFs are text-only by default (pages never rendered to images unless `--images`).
- Incremental reprocessing: uploading extra files to a finished run reprocesses only new/changed files (per-file content hashes) and merges line items.
- RFQ email is generated deterministically (no API calls).

## Env loading
- Both `app.py` and `cli.py` call `dotenv.load_dotenv()` if available. `.env` lives at repo root.