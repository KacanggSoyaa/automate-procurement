"""End-to-end ITB -> specification sheet pipeline shared by the API and CLI.

Supports incremental mode: when ``previous`` (a persisted job record) is given,
only files that are new or whose content changed since the last run are
extracted and classified; their line items and requirements are merged into
the stored results before the specification sheet and RFQ email are rebuilt.
"""
import hashlib
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extractors.pdf_extractor import PDFExtractor  # noqa: E402
from extractors.office_extractor import OfficeExtractor  # noqa: E402
from processors.ai_processor import AIProcessor  # noqa: E402
from generators.enhanced_spec_sheet import EnhancedSpecSheetGenerator  # noqa: E402
from generators.rfq_email_generator import RFQEmailGenerator  # noqa: E402
from server.ai_providers import provider_label  # noqa: E402

ProgressCb = Optional[Callable[[str, int, int, str], None]]


def _normalise_skip(skip_files: Optional[List[str]]) -> set:
    """Normalise user-listed filenames for case-insensitive exact matching."""
    if not skip_files:
        return set()
    return {str(name).strip().lower() for name in skip_files if str(name).strip()}


def _digest(path: str) -> str:
    """Return a sha256 of a file, or '' when it cannot be read."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception:
        return ""


def _dedupe_strs(values: List[str]) -> List[str]:
    """Remove blank/near-duplicate strings while keeping the first wording."""
    seen, out = set(), []
    for v in values:
        key = " ".join(str(v).lower().split())
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _dedupe_items(items: List[Dict]) -> List[Dict]:
    """Deduplicate line item dicts across runs by description/number/qty."""
    seen, out = set(), []
    for item in items:
        desc = " ".join(str(item.get("description") or item.get("item_name") or "").lower().split())
        key = (desc, item.get("item_number"), item.get("qty"))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _merge_meta(prev: Dict, fresh: Dict) -> Dict:
    """Merge meta fields, keeping previously stored values (first run wins)."""
    merged = dict(fresh or {})
    merged.update(prev or {})
    return merged


def rebuild_artifacts(data: Dict, output_path: str) -> Dict:
    """Rebuild derived counts, RFQ emails and the spec sheet after manual edits."""
    rebuilt = dict(data)
    items = list(rebuilt.get("line_items") or [])
    rebuilt["line_items"] = items
    rebuilt["line_items_count"] = len(items)
    rebuilt["rfq_emails"] = RFQEmailGenerator().build_emails(rebuilt)
    EnhancedSpecSheetGenerator().generate(rebuilt, output_path)
    return rebuilt


def run_pipeline(
    input_dir: str,
    output_path: str,
    model: Optional[str] = None,
    include_images: bool = True,
    pattern: str = "*",
    skip_files: Optional[List[str]] = None,
    progress: ProgressCb = None,
    previous: Optional[Dict] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict:
    """Run the full ITB -> spec sheet pipeline for a folder of uploaded files.

    Every matching PDF, Word (.docx) and Excel (.xlsx/.xlsm) file is read by
    default. ``skip_files`` lets the caller exclude specific documents by exact
    filename (case-insensitive); skipped files are still listed in the source
    footer as evidence but are never sent to the AI provider for classification.

    Pass ``previous`` (a persisted job record with ``data`` and ``config``) to
    reprocess incrementally: only files added or changed since then are
    classified, and their results are merged into the stored ones.
    """
    prev_record = previous or {}
    prev_data = prev_record.get("data") or {}
    prev_cfg = prev_record.get("config") or {}
    prev_processed = prev_cfg.get("processed") or {}
    processed = dict(prev_processed)

    def emit(stage: str, current: int, total: int, message: str):
        """Forward a progress update to the caller's callback, if any."""
        if progress:
            progress(stage, current, total, message)

    pdf_ext = PDFExtractor()
    office_ext = OfficeExtractor()

    emit("extract", 0, 1, "Scanning uploaded PDF / Word / Excel files...")
    results = pdf_ext.extract_itb_folder(input_dir, pattern=pattern)
    results += office_ext.extract_office_folder(input_dir, pattern=pattern)
    if not results:
        raise RuntimeError(
            f"No readable PDF, Word or Excel files matched '{pattern}' in the upload."
        )
    errors = [r for r in results if r.get("error")]
    for r in errors:
        emit("extract", 0, 1, f"Skipped {r['filename']}: {r['error']}")
    ok = [r for r in results if not r.get("error")]
    emit("extract", 1, 1, f"Read {len(ok)} file(s)")

    # Every PDF is read by default. Only filenames the user explicitly listed
    # in the settings are excluded (exact match, case-insensitive), so the real
    # item document is never skipped by mistake.
    skipped = _normalise_skip(skip_files)
    docs = [r for r in ok if r["filename"].strip().lower() not in skipped]
    for r in ok:
        if r["filename"].strip().lower() in skipped:
            emit("extract", 1, 1, f"Skipped by settings: {r['filename']}")

    # Incremental mode: only read/classify files whose name+content we have
    # not handled before. A re-uploaded file with the same name but different
    # content counts as new so its items are re-extracted.
    doc_hashes = {r["filename"]: _digest(r["path"]) for r in docs}
    new_docs = [r for r in docs if prev_processed.get(r["filename"]) != doc_hashes[r["filename"]]]
    for r in new_docs:
        processed[r["filename"]] = doc_hashes[r["filename"]]
    if new_docs:
        names = ", ".join(r["filename"] for r in new_docs)
        emit("extract", 1, 1, f"New/changed file(s): {names}")
    content = "\n\n".join(r.get("content", "") for r in new_docs)

    # Every uploaded document is kept as evidence for the source footer.
    # Preserve previously recorded names to avoid duplicates on re-runs.
    source_files = list(prev_data.get("source_files") or [])
    for r in ok:
        if r["filename"] not in source_files:
            source_files.append(r["filename"])

    image_paths = []
    if include_images:
        emit("images", 0, 1, "Collecting images / screenshots...")
        screenshots = pdf_ext.collect_image_files(input_dir)
        new_screens = []
        for p in screenshots:
            name = Path(p).name
            if prev_processed.get(name) != _digest(p):
                new_screens.append(p)
                processed[name] = _digest(p)
        image_paths += new_screens
        for p in new_screens:
            if Path(p).name not in source_files:
                source_files.append(Path(p).name)
        emit("images", 1, 1, f"Found {len(new_screens)} new image(s)")

    processor = AIProcessor(provider=provider, model=model, api_key=api_key)
    label = provider_label(processor.provider)

    def ai_progress(kind: str, i: int, n: int):
        emit("classify", i, n, f"Classifying {kind} {i}/{n} with {label}")

    reqs = processor.classify(content, image_paths=image_paths, progress=ai_progress)

    # Merge fresh results into the previously stored ones.
    line_items = _dedupe_items((prev_data.get("line_items") or []) + reqs["line_items"])
    merged = {
        "files_processed": len(ok),
        "summary": f"Analyzed {len(ok)} ITB document(s)",
        "source_files": source_files,
        "meta": _merge_meta(prev_data.get("meta") or {}, reqs.get("meta") or {}),
        "line_items": line_items,
        "line_items_count": len(line_items),
        "technical_requirements": _dedupe_strs(
            (prev_data.get("technical_requirements") or []) + reqs["technical"]
        ),
        "submission_rules": _dedupe_strs(
            (prev_data.get("submission_rules") or []) + reqs["submission"]
        ),
        "mandatory_requirements": _dedupe_strs(
            (prev_data.get("mandatory_requirements") or []) + reqs["mandatory"]
        ),
        "commercial_requirements": _dedupe_strs(
            (prev_data.get("commercial_requirements") or []) + reqs["commercial"]
        ),
        "dates": _dedupe_strs((prev_data.get("dates") or []) + reqs["dates"]),
        "suppliers": prev_data.get("suppliers") or [],
    }

    # One copy-ready RFQ email per line item (deterministic, no API calls).
    merged["rfq_emails"] = RFQEmailGenerator().build_emails(merged)

    emit("generate", 0, 1, "Generating specification sheet...")
    generator = EnhancedSpecSheetGenerator()
    out = generator.generate(merged, output_path)
    emit("generate", 1, 1, "Specification sheet ready")

    return {"output_path": out, "data": merged, "processed": processed}