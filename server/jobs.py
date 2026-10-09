"""In-memory job queue that runs the extraction pipeline in a thread pool."""
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .pipeline import run_pipeline

# Where uploaded files and per-job output workspaces are stored.
UPLOAD_ROOT = Path("./data/uploads")
WORKSPACE_ROOT = Path("./data/workspaces")


@dataclass
class Job:
    """State for a single extraction job, as seen by the API and the UI."""
    id: str
    status: str = "queued"
    stage: str = "queued"
    current: int = 0
    total: int = 0
    message: str = "Queued"
    logs: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    output_path: Optional[str] = None
    files: List[str] = field(default_factory=list)
    data: Optional[Dict] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """Serialise the job for the JSON API (keeps only the last 50 logs)."""
        return {
            "id": self.id,
            "status": self.status,
            "stage": self.stage,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "logs": self.logs[-50:],
            "error": self.error,
            "files": self.files,
            "result": self._result_summary(),
            "created_at": self.created_at,
        }

    def _result_summary(self):
        """Return the trimmed result payload, or None while the job runs."""
        if self.status != "done" or not self.data:
            return None
        d = self.data
        return {
            "files_processed": d.get("files_processed", 0),
            "source_files": d.get("source_files", []),
            "line_items_count": d.get("line_items_count", 0),
            "line_items": d.get("line_items", [])[:100],
            "meta": d.get("meta", {}),
            "technical_count": len(d.get("technical_requirements", [])),
            "submission_count": len(d.get("submission_rules", [])),
            "mandatory_count": len(d.get("mandatory_requirements", [])),
            "has_output": bool(self.output_path),
        }


class JobManager:
    """Creates jobs, saves uploads and executes the pipeline in the background."""

    def __init__(self, max_workers: int = 2):
        """Set up the in-memory job store and the worker thread pool."""
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    def create(self, files: List, model: Optional[str] = None, include_images: bool = True,
               pattern: str = "*", skip_files: Optional[List[str]] = None) -> Job:
        """Save the uploaded files, register a job and start it in the pool."""
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id)
        upload_dir = UPLOAD_ROOT / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Stream each upload to disk in 1MB blocks to handle large files.
        for f in files:
            name = Path(f.filename).name
            if not name:
                continue
            dest = upload_dir / name
            with open(dest, "wb") as out:
                while True:
                    chunk = f.file.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            job.files.append(name)

        with self._lock:
            self._jobs[job_id] = job

        workspace = WORKSPACE_ROOT / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        output_path = workspace / "specification_sheet.docx"

        self._pool.submit(
            self._run, job, str(upload_dir), str(output_path), model, include_images,
            pattern, skip_files,
        )
        return job

    def _run(self, job: Job, upload_dir: str, output_path: str, model, include_images, pattern,
             skip_files: Optional[List[str]] = None):
        """Execute the pipeline for one job, updating state and logging errors."""
        self._update(job, status="running", stage="start", message="Starting pipeline")
        try:
            result = run_pipeline(
                input_dir=upload_dir,
                output_path=output_path,
                model=model,
                include_images=include_images,
                pattern=pattern,
                skip_files=skip_files,
                progress=lambda stage, cur, tot, msg: self._update(
                    job, stage=stage, current=cur, total=tot, message=msg, log=msg
                ),
            )
            self._update(
                job,
                status="done",
                stage="done",
                message="Specification sheet generated",
                output_path=result["output_path"],
                data=result["data"],
                log="Pipeline complete",
            )
        except Exception as e:
            self._update(
                job,
                status="error",
                stage="error",
                message=str(e),
                error=f"{type(e).__name__}: {e}",
                log=f"ERROR: {e}",
            )
            traceback.print_exc()

    def _update(self, job: Job, log: Optional[str] = None, **fields):
        """Thread-safely set job fields and optionally append a timestamped log."""
        with self._lock:
            for key, val in fields.items():
                if val is not None:
                    setattr(job, key, val)
            if log:
                job.logs.append({"ts": datetime.now().strftime("%H:%M:%S"), "message": log})

    def get(self, job_id: str) -> Optional[Job]:
        """Look up a job by id, or return None if it does not exist."""
        with self._lock:
            return self._jobs.get(job_id)


job_manager = JobManager()
