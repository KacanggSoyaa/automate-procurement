"""On-disk history of completed extraction jobs.

Keeps a lightweight index (``data/history.json``) for fast listing plus a full
record (``data/workspaces/<job_id>/job.json``) per run so past ITBs can be
reopened — and their specification sheet downloaded — after a backend restart.
"""
import json
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Optional

DATA_ROOT = Path("./data")
WORKSPACE_ROOT = DATA_ROOT / "workspaces"
INDEX_PATH = DATA_ROOT / "history.json"


def _title_and_subtitle(job) -> tuple:
    """Derive a human-readable title and subtitle for a job's history entry."""
    data = job.data or {}
    meta = data.get("meta") or {}
    title = (meta.get("project_title") or "").strip()
    if not title:
        title = (meta.get("project_ref") or "").strip()
    if not title and job.files:
        title = job.files[0]
    if not title:
        title = "Untitled ITB"

    bits: List[str] = []
    ref = (meta.get("project_ref") or "").strip()
    if ref and ref != title:
        bits.append(ref)
    buyer = (meta.get("buyer") or "").strip()
    if buyer:
        bits.append(buyer)
    if not bits:
        n = len(job.files)
        bits.append(f"{n} file" + ("" if n == 1 else "s"))
    return title, " · ".join(bits)


class HistoryStore:
    """Persists finished jobs to disk and serves the sidebar history list."""

    def __init__(self, workspace_root: Path = None, index_path: Path = None):
        """Resolve storage paths and load the existing index into memory."""
        self.workspace_root = Path(workspace_root) if workspace_root else WORKSPACE_ROOT
        self.index_path = Path(index_path) if index_path else INDEX_PATH
        self._lock = threading.Lock()
        self._index: List[Dict] = self._read_index()

    def _read_index(self) -> List[Dict]:
        """Read the index file, returning an empty list if missing or corrupt."""
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    def _write_index(self):
        """Persist the in-memory index to disk."""
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.index_path.write_text(
                json.dumps(self._index, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def save(self, job):
        """Persist a job's full record and upsert its index entry."""
        record = {
            "id": job.id,
            "status": job.status,
            "stage": job.stage,
            "current": job.current,
            "total": job.total,
            "message": job.message,
            "logs": job.logs[-100:],
            "error": job.error,
            "files": job.files,
            "created_at": job.created_at,
            "output_path": job.output_path,
            "config": job.config,
            "data": job.data,
        }
        entry = record.copy()
        entry.pop("logs", None)
        entry.pop("data", None)

        title, subtitle = _title_and_subtitle(job)
        data = job.data or {}
        entry.update({
            "title": title,
            "subtitle": subtitle,
            "line_items_count": data.get("line_items_count", len(data.get("line_items", []) or [])),
            "files_count": len(job.files),
            "project_ref": (data.get("meta") or {}).get("project_ref"),
            "buyer": (data.get("meta") or {}).get("buyer"),
        })

        with self._lock:
            workspace = self.workspace_root / job.id
            try:
                workspace.mkdir(parents=True, exist_ok=True)
                (workspace / "job.json").write_text(
                    json.dumps(record, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
            self._index = [e for e in self._index if e.get("id") != job.id]
            self._index.insert(0, entry)
            self._write_index()
        return entry

    def list(self) -> List[Dict]:
        """Return history entries, newest first."""
        with self._lock:
            return list(self._index)

    def load(self, job_id: str) -> Optional[Dict]:
        """Return a job's full persisted record, or None if unknown."""
        path = self.workspace_root / job_id / "job.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def rename(self, job_id: str, title: str) -> Optional[Dict]:
        """Set a custom title for a history entry and persist the change."""
        title = (title or "").strip()
        if not title:
            return None
        with self._lock:
            entry = next((e for e in self._index if e.get("id") == job_id), None)
            if entry is None:
                return None
            entry["title"] = title
            self._write_index()

        # Keep the full record in sync so the name survives a reload.
        record_path = self.workspace_root / job_id / "job.json"
        try:
            rec = json.loads(record_path.read_text(encoding="utf-8"))
            rec["title"] = title
            record_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        except Exception:
            pass
        return entry

    def delete(self, job_id: str) -> bool:
        """Remove a job from the index, disk record and workspace. Returns success."""
        with self._lock:
            before = len(self._index)
            self._index = [e for e in self._index if e.get("id") != job_id]
            removed = len(self._index) != before
            self._write_index()
        workspace = self.workspace_root / job_id
        try:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
        except Exception:
            pass
        return removed


history_store = HistoryStore()
