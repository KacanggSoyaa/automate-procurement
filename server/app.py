"""FastAPI backend for the Automate Procurement web UI."""
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .jobs import job_manager


class RenameRequest(BaseModel):
    """Body for renaming a saved history entry."""
    title: str

app = FastAPI(title="Automate Procurement API", version="0.1.0")

# The Vite dev server runs on a different port, so allow cross-origin calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """Liveness probe used to check the backend is up."""
    return {"status": "ok"}


def _parse_skip_files(raw: Optional[str]) -> List[str]:
    """Split the settings textarea into a clean list of filenames to skip."""
    if not raw:
        return []
    parts = raw.replace(",", "\n").splitlines()
    return [p.strip() for p in parts if p.strip()]


@app.post("/api/jobs")
async def create_job(
    files: List[UploadFile] = File(...),
    model: Optional[str] = Form(None),
    include_images: bool = Form(True),
    pattern: str = Form("*"),
    skip_files: Optional[str] = Form(None),
):
    """Accept an uploaded ITB folder and queue a processing job.

    ``skip_files`` is a newline- or comma-separated list of exact filenames the
    user chose to exclude from item extraction.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    job = job_manager.create(
        files,
        model=model,
        include_images=include_images,
        pattern=pattern,
        skip_files=_parse_skip_files(skip_files),
    )
    return job.to_dict()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Return the current status, logs and results of a job."""
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_dict()


@app.get("/api/history")
def list_history():
    """Return the saved history of finished ITB runs, newest first."""
    return {"jobs": job_manager.history()}


@app.delete("/api/history/{job_id}")
def delete_history(job_id: str):
    """Remove a run from the history list and delete its stored workspace."""
    if not job_manager.delete(job_id):
        raise HTTPException(status_code=404, detail="History entry not found.")
    return {"ok": True, "id": job_id}


@app.patch("/api/history/{job_id}")
def rename_history(job_id: str, body: RenameRequest):
    """Rename a saved history entry (sets a custom display title)."""
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title must not be empty.")
    entry = job_manager.rename(job_id, title)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return entry


@app.post("/api/jobs/{job_id}/files")
async def add_job_files(job_id: str, files: List[UploadFile] = File(...)):
    """Append files to a finished job's folder and reprocess only the new ones."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    job = job_manager.add_and_reprocess(job_id, files)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/versions/{n}/download")
def download_version(job_id: str, n: int):
    """Download a historical version snapshot (zip) of a finished job."""
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    zip_path = job_manager.version_zip(job_id, n)
    if zip_path is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"specification_sheet_{zip_path.stem}_{job_id}.zip",
    )


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    """Stream the generated specification sheet DOCX for a finished job."""
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "done" or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(status_code=409, detail="Result not ready.")
    return FileResponse(
        job.output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="specification_sheet.docx",
    )
