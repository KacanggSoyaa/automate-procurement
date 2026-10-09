# Automate Procurement Process

Automated system for RFQ/ITB procurement workflow with Python.

## Features

- **Step 1**: ITB Review & Line Item Extraction (PDF parsing)
- **Step 2**: Specification Sheet & Reference Document Generation (Word DOCX)
- **Step 3**: Vendor Sourcing & RFQ Dispatch (CSV management)

## Quick Start

1. Place your ITB/PDF files in data/itb/
2. Run the complete workflow:
   `ash
   python cli.py run-all
   `
3. Edit data/vendors/vendor_list.csv with vendor details
4. Dispatch RFQs:
   `ash
   python cli.py dispatch
   `

## Commands

- python cli.py analyze - Analyze ITB files
- python cli.py extract - Extract & generate spec sheet (Steps 1-2)
- python cli.py setup-vendors - Create vendor template
- python cli.py dispatch - Prepare RFQ dispatch package
- python cli.py run-all - Run complete workflow

## Output Files

- outputs/specification_sheet.docx - Generated spec sheet
- data/vendors/vendor_list.csv - Vendor database
- outputs/rfq_packages/rfq_summary.json - RFQ dispatch summary

## Web UI (drag & drop)

Drag an ITB folder into the browser; the pipeline runs in the background and the finished
DOCX is downloadable. Two processes:

1. Backend (FastAPI):
   ```bash
   pip install -r requirements.txt
   uvicorn server.app:app --reload --port 8000
   ```
2. Frontend (Vite + React):
   ```bash
   cd web
   npm install
   npm run dev
   ```

The dev server proxies `/api` to `http://localhost:8000`.

## Configuration

Create a `.env` in the project root (git-ignored):

```
GEMINI_API_KEY=your-key-from-aistudio
GEMINI_MODEL=gemini-3.8-flash
```

Get a key at https://aistudio.google.com/apikey. The **free tier allows only ~20
requests/day per model**, so the processor falls back across `GEMINI_MODEL` and the
models in `AIProcessor.FALLBACK_MODELS`. Results are cached in `data/.ai_cache/`, so
re-runs of the same ITB do not spend quota. Enable billing on the Google Cloud project
for higher throughput.
