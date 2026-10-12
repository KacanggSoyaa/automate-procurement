"""In-memory job queue that runs the extraction pipeline in a thread pool."""
import shutil
import threading
import traceback
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .history import history_store
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
    config: Optional[Dict] = None
    versions: List[Dict] = field(default_factory=list)
    audit: List[Dict] = field(default_factory=list)
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
            "versions": self.versions,
            "audit": self.audit[-100:],
            "created_at": self.created_at,
        }

    @classmethod
    def from_record(cls, record: Dict) -> "Job":
        """Rebuild a Job from a persisted history record (for reload after restart)."""
        return cls(
            id=record.get("id", ""),
            status=record.get("status", "done"),
            stage=record.get("stage", "done"),
            current=record.get("current", 0),
            total=record.get("total", 0),
            message=record.get("message", ""),
            logs=record.get("logs", []),
            error=record.get("error"),
            output_path=record.get("output_path"),
            files=record.get("files", []),
            data=record.get("data"),
            config=record.get("config"),
            versions=record.get("versions", []),
            audit=record.get("audit", []),
            created_at=record.get("created_at", ""),
        )

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
            "rfq_emails": d.get("rfq_emails", []),
            "meta": d.get("meta", {}),
            "technical_count": len(d.get("technical_requirements", [])),
            "submission_count": len(d.get("submission_rules", [])),
            "mandatory_count": len(d.get("mandatory_requirements", [])),
            "suppliers": d.get("suppliers", []),
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

        if job.files:
            more = "…" if len(job.files) > 3 else ""
            self._audit(
                job,
                "run_created",
                f"{len(job.files)} file(s) uploaded: {', '.join(job.files[:3])}{more}",
            )

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
            job.config = self._build_config(model, include_images, pattern, skip_files, result["processed"])
            self._update(
                job,
                status="done",
                stage="done",
                message="Specification sheet generated",
                output_path=result["output_path"],
                data=result["data"],
                log="Pipeline complete",
            )
            v = self._snapshot_version(job, "run")
            self._audit(
                job,
                "run_completed",
                f"Specification sheet saved as {v['tag']}",
                version=v["id"] if v else None,
            )
            history_store.save(job)
        except Exception as e:
            job.config = self._build_config(model, include_images, pattern, skip_files, {})
            self._update(
                job,
                status="error",
                stage="error",
                message=str(e),
                error=f"{type(e).__name__}: {e}",
                log=f"ERROR: {e}",
            )
            self._audit(job, "run_failed", str(e))
            history_store.save(job)
            traceback.print_exc()

    @staticmethod
    def _build_config(model, include_images, pattern, skip_files, processed: Dict) -> Dict:
        """Capture the settings that produced a run, incl. processed file hashes."""
        return {
            "model": model,
            "include_images": include_images,
            "pattern": pattern,
            "skip_files": list(skip_files or []),
            "processed": processed,
        }

    def add_and_reprocess(self, job_id: str, files: List) -> Optional[Job]:
        """Append files to a finished job's folder and reprocess only the new ones."""
        job = self.get(job_id)
        if job is None:
            return None

        upload_dir = UPLOAD_ROOT / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        added = 0
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
            if name not in job.files:
                job.files.append(name)
            added += 1

        if not added:
            return job
        # Refuse to stack a second incremental run while one is already going.
        if job.status in ("queued", "running"):
            return job

        record = history_store.load(job_id) or {}
        cfg = job.config or (record.get("config") or {})
        self._audit(job, "files_added", f"{added} file(s) added, reprocessing queued")
        self._update(
            job,
            status="queued",
            stage="queued",
            current=0,
            total=0,
            message="Adding files…",
            log=f"{added} file(s) added — reprocessing",
        )
        self._pool.submit(self._run_incremental, job, cfg, record)
        return job

    def _run_incremental(self, job: Job, cfg: Dict, record: Dict):
        """Reprocess only new/changed files for a finished job and save results."""
        upload_dir = str(UPLOAD_ROOT / job.id)
        output_path = job.output_path or str(WORKSPACE_ROOT / job.id / "specification_sheet.docx")
        self._update(job, status="running", stage="start", message="Reprocessing new files")
        try:
            result = run_pipeline(
                input_dir=upload_dir,
                output_path=output_path,
                model=cfg.get("model"),
                include_images=cfg.get("include_images", True),
                pattern=cfg.get("pattern", "*"),
                skip_files=cfg.get("skip_files"),
                previous=record,
                progress=lambda stage, cur, tot, msg: self._update(
                    job, stage=stage, current=cur, total=tot, message=msg, log=msg
                ),
            )
            job.config = {**cfg, "processed": result["processed"]}
            self._update(
                job,
                status="done",
                stage="done",
                message="Specification sheet updated",
                output_path=result["output_path"],
                data=result["data"],
                log="Incremental reprocess complete",
            )
            v = self._snapshot_version(job, "reprocess")
            self._audit(
                job,
                "reprocess_completed",
                f"Updated specification sheet saved as {v['tag']}",
                version=v["id"] if v else None,
            )
            history_store.save(job)
        except Exception as e:
            self._update(
                job,
                status="error",
                stage="error",
                message=str(e),
                error=f"{type(e).__name__}: {e}",
                log=f"ERROR: {e}",
            )
            self._audit(job, "reprocess_failed", str(e))
            history_store.save(job)
            traceback.print_exc()

    def _snapshot_version(self, job: Job, reason: str) -> Optional[Dict]:
        """Copy a finished run's output files into an immutable, versioned folder.

        Returns a ``{id, tag, ts, reason, files, ...}`` summary, or None when
        the run produced no output file.
        """
        out = Path(job.output_path) if job.output_path else WORKSPACE_ROOT / job.id / "specification_sheet.docx"
        wdir = out.parent
        if not wdir.is_dir() or not out.exists():
            return None
        with self._lock:
            n = max((v["id"] for v in job.versions), default=0) + 1
        vdir = wdir / "versions" / f"v{n:02d}"
        vdir.mkdir(parents=True, exist_ok=True)
        copied: List[str] = []
        for f in sorted(wdir.iterdir()):
            if f.is_file() and f.name != "job.json":
                try:
                    shutil.copy2(f, vdir / f.name)
                    copied.append(f.name)
                except Exception:
                    continue
        version = {
            "id": n,
            "tag": f"v{n:02d}",
            "ts": datetime.now().isoformat(timespec="seconds"),
            "reason": reason,
            "files": copied,
            "files_processed": (job.data or {}).get("files_processed", 0),
            "line_items_count": (job.data or {}).get("line_items_count", 0),
        }
        with self._lock:
            job.versions.append(version)
        return version

    def _audit(self, job: Job, action: str, detail: str = "", version: Optional[int] = None):
        """Append an immutable event to a job's audit trail."""
        event = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "actor": "system",
            "action": action,
            "detail": detail,
        }
        if version is not None:
            event["version"] = version
        with self._lock:
            job.audit.append(event)

    def version_zip(self, job_id: str, n: int) -> Optional[Path]:
        """Return (creating on demand) the zip snapshot for one version, or None."""
        vdir = WORKSPACE_ROOT / job_id / "versions" / f"v{n:02d}"
        if not vdir.is_dir():
            return None
        zip_path = vdir.parent / f"v{n:02d}.zip"
        if not zip_path.exists():
            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in sorted(vdir.iterdir()):
                        if f.is_file():
                            z.write(f, arcname=f"{vdir.name}/{f.name}")
            except Exception:
                return None
        return zip_path

    def _update(self, job: Job, log: Optional[str] = None, **fields):
        """Thread-safely set job fields and optionally append a timestamped log."""
        with self._lock:
            for key, val in fields.items():
                if val is not None:
                    setattr(job, key, val)
            if log:
                job.logs.append({"ts": datetime.now().strftime("%H:%M:%S"), "message": log})

    def get(self, job_id: str) -> Optional[Job]:
        """Look up a live job, or rebuild one from persisted history."""
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None:
            return job
        record = history_store.load(job_id)
        if record is None:
            return None
        loaded = Job.from_record(record)
        with self._lock:
            self._jobs[job_id] = loaded
        return loaded

    def history(self) -> List[Dict]:
        """Return the persisted history index (newest first)."""
        return history_store.list()

    def delete(self, job_id: str) -> bool:
        """Drop a job from memory and disk, returning whether it existed."""
        with self._lock:
            self._jobs.pop(job_id, None)
        return history_store.delete(job_id)

    def rename(self, job_id: str, title: str) -> Optional[Dict]:
        """Rename a saved history entry; returns the updated entry or None."""
        return history_store.rename(job_id, title)


job_manager = JobManager()
