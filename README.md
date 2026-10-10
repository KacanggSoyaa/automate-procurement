# Automate Procurement

Reads an ITB / RFQ package (PDF, Word, Excel and screenshots), extracts the real
line items with Gemini, writes a formatted RFQ specification sheet, and drafts a
copy-ready quotation request email.

## What it does

1. **Read** every uploaded document — PDF (`text + rendered pages`), Word
   (`.docx`), Excel (`.xlsx`/`.xlsm`) and images/screenshots (`.png/.jpg/.jpeg/.webp/.bmp`).
2. **Classify** with Gemini: separate genuine purchasable line items from
   requirements, rules and boilerplate; extract project metadata.
- Skip specific documents by exact filename (Settings panel) if a folder
  contains terms/HSE/guide docs you do not want read.
- Produce a formatted **specification sheet** (`.docx`).
- Generate one **copy-ready RFQ email** covering all line items.

## Requirements

- Python 3.10+ (developed on 3.14)
- Node.js 18+ (for the web UI)
- A Gemini API key: https://aistudio.google.com/apikey

## Setup

```powershell
# from the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

# frontend deps
cd web; npm install; cd ..
```

Create a `.env` file in the repo root (gitignored):

```
GEMINI_API_KEY=your_key_here
# optional:
GEMINI_MODEL=gemini-3.8-flash
RFQ_SIGNATURE=Best regards,
Procurement Team
```

## Run — Web UI (recommended)

Two processes, from the repo root (keep the first terminal open):

```powershell
# 1) backend  (http://localhost:8000)
python -m uvicorn server.app:app --reload --port 8000
```

```
cd web
npm run dev
```

Then open **http://localhost:5173** (Vite proxies `/api` → `:8000`):

1. Drag in an ITB folder or select files (PDF / Word / Excel / images).
2. Optionally click documents in **Settings · Skip Files** (or type exact filenames) to exclude them.
3. Click **RUN PIPELINE** — progress streams live.
4. When done: **Download specification sheet (.docx)** and copy the generated **quotation email**.

To build the frontend for production: `cd web; npm run build` (output in `web/dist`).

## CLI

```powershell
# Extract ITB content and generate the spec sheet
python cli.py extract --itb-dir ./data/itb --pattern "*ITB*" --skip "GTC.pdf,Exhibit V.pdf"

# List what matches a folder and how much text each file yields
python cli.py analyze --itb-dir ./data/itb --pattern "*ITB*"

# Step 3: vendors + RFQ package
python cli.py setup-vendors
python cli.py dispatch --spec-sheet ./outputs/specification_sheet.docx

# Full workflow (extract + setup vendors)
python cli.py run-all
```

`extract` options: `--itb-dir`, `--output`, `--pattern` (default `*ITB*`), `--images`, `--no-images`, `--model`, `--skip`.

## Configuration

`.env` (repo root, gitignored):

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | yes | https://aistudio.google.com/apikey |
| `GEMINI_MODEL` | no | defaults to `gemini-3.8-flash` |
| `RFQ_SIGNATURE` | no | signature block for the quotation email |

Free-tier Gemini quota is ~20 requests/day **per model**. The processor falls back through
several models and caches results in `data/.ai_cache/`, so repeat runs cost no extra quota.

## Project structure

```
server/            FastAPI backend (app.py, jobs.py, pipeline.py)
processors/        Gemini classification (ai_processor.py)
extractors/        PDF (pdf_extractor.py) + Word/Excel (office_extractor.py)
generators/        Spec sheet (enhanced_spec_sheet.py), RFQ email (rfq_email_generator.py),
                   RFQ dispatch (rfq_dispatcher.py), layout reference (technicalSpecFormat.py)
cli.py             Command-line entry point
web/               Vite + React + Tailwind UI
data/              uploads, workspaces, vendor list, AI cache (gitignored)
outputs/           Generated documents (gitignored)
```

## Notes

- `data/itb/`, `data/uploads/`, `data/workspaces/`, `data/.ai_cache/` and `outputs/` are gitignored and may hold
  confidential bid documents — never commit them.
- The web backend keeps jobs in memory; restarting it clears job history.
- The RFQ email is generated deterministically (no API calls) — one email covering all line items.
