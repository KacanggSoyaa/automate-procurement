"""Persisted master list of suppliers the buyer curates by hand.

Unlike ``server/suppliers.py`` (which searches the live web for a specific ITB),
this store is a durable directory of vendors the user wants to keep and reuse.
Entries can be added manually from the UI or imported from a run's supplier
shortlist, and they survive restarts via ``data/suppliers.json``.
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DATA_ROOT = Path("./data")
STORE_PATH = DATA_ROOT / "suppliers.json"

# Order of the user-editable text fields; used to normalise incoming payloads.
_FIELDS = ("company_name", "website", "email", "contact", "source", "notes", "tags")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean(value) -> str:
    return (value or "").strip() if isinstance(value, str) else ""


class SupplierStore:
    """Thread-safe, file-backed directory of curated suppliers."""

    def __init__(self, path: Path = None):
        self.path = Path(path) if path else STORE_PATH
        self._lock = threading.Lock()
        self._items: List[Dict] = self._read()

    def _read(self) -> List[Dict]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    def _write(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._items, indent=2), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _normalise(payload: Dict, base: Optional[Dict] = None) -> Dict:
        """Merge an incoming payload over an existing entry, trimming strings."""
        item = dict(base or {})
        for field in _FIELDS:
            if field in payload:
                item[field] = _clean(payload.get(field))
        item.setdefault("company_name", "")
        item.setdefault("website", "")
        item.setdefault("email", "")
        item.setdefault("contact", "")
        item.setdefault("source", "")
        item.setdefault("notes", "")
        item.setdefault("tags", "")
        return item

    def list(self, owner: Optional[str] = None, scope: str = "mine") -> List[Dict]:
        """Return curated suppliers (newest first), filtered by ownership.

        ``scope="mine"`` returns the caller's own suppliers plus any shared
        entries that have no owner (legacy rows). ``scope="all"`` returns every
        supplier regardless of owner. Entries carry an ``owner`` field so the UI
        can mark which ones belong to someone else.
        """
        with self._lock:
            items = list(self._items)
        if scope == "all":
            return items
        return [s for s in items if not s.get("owner") or s.get("owner") == owner]

    def get(self, supplier_id: str) -> Optional[Dict]:
        with self._lock:
            return next((s for s in self._items if s.get("id") == supplier_id), None)

    @staticmethod
    def _can_write(entry: Optional[Dict], owner: Optional[str]) -> bool:
        """A supplier is writable by its owner, or by anyone when unowned/shared."""
        if entry is None:
            return False
        return not entry.get("owner") or entry.get("owner") == owner

    def add(self, payload: Dict, owner: Optional[str] = None) -> Optional[Dict]:
        """Add one supplier. Returns the entry, or None if it has no name/website."""
        item = self._normalise(payload)
        if not item["company_name"] and not item["website"]:
            return None
        item["id"] = uuid.uuid4().hex[:12]
        item["owner"] = owner or ""
        item["created_at"] = _now()
        item["updated_at"] = item["created_at"]
        with self._lock:
            self._items.insert(0, item)
            self._write()
        return item

    def add_many(self, payloads: List[Dict], owner: Optional[str] = None) -> Dict:
        """Bulk-add suppliers (e.g. a whole run shortlist); skips blanks/dupes.

        A supplier is considered a duplicate when its (case-insensitive) website
        domain OR company name already exists in the directory.
        """
        added, skipped = 0, 0
        with self._lock:
            existing = {
                self._key(s) for s in self._items
            }
            for payload in payloads or []:
                item = self._normalise(payload)
                if not item["company_name"] and not item["website"]:
                    skipped += 1
                    continue
                key = self._key(item)
                if key and key in existing:
                    skipped += 1
                    continue
                item["id"] = uuid.uuid4().hex[:12]
                item["owner"] = owner or ""
                item["created_at"] = _now()
                item["updated_at"] = item["created_at"]
                self._items.insert(0, item)
                if key:
                    existing.add(key)
                added += 1
            if added:
                self._write()
        return {"added": added, "skipped": skipped, "total": len(self._items)}

    @staticmethod
    def _key(item: Dict) -> str:
        """Dedupe key: website domain first, else the normalised company name."""
        website = _clean(item.get("website")).lower()
        if website:
            return website.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
        name = " ".join(_clean(item.get("company_name")).lower().split())
        return name

    def update(self, supplier_id: str, payload: Dict, owner: Optional[str] = None) -> Optional[Dict]:
        """Patch one supplier's fields. Returns the updated entry or None.

        Shared (unowned) entries and the caller's own entries are editable;
        another user's entry is left untouched (returns None).
        """
        with self._lock:
            idx = next((i for i, s in enumerate(self._items) if s.get("id") == supplier_id), None)
            if idx is None or not self._can_write(self._items[idx], owner):
                return None
            updated = self._normalise(payload, base=self._items[idx])
            updated["updated_at"] = _now()
            self._items[idx] = updated
            self._write()
            return updated

    def delete(self, supplier_id: str, owner: Optional[str] = None) -> bool:
        """Remove a supplier the caller may write. Returns whether it was removed."""
        with self._lock:
            entry = next((s for s in self._items if s.get("id") == supplier_id), None)
            if not self._can_write(entry, owner):
                return False
            before = len(self._items)
            self._items = [s for s in self._items if s.get("id") != supplier_id]
            removed = len(self._items) != before
            if removed:
                self._write()
            return removed


supplier_store = SupplierStore()
